import torch
from torch import optim
from torch.utils.data import ConcatDataset
import numpy as np
import tqdm
import copy
import utils
import time
from data import SubDataset, ExemplarDataset
from continual_learner import ContinualLearner
import evaluate
import datetime
import os
import csv
import datetime
output=[]
output5=[]

def train_cl(model, train_datasets, test_datasets, replay_mode="none", scenario="domain", classes_per_task=None, iters=2000, batch_size=32,
             generator=None, gen_iters=0, gen_loss_cbs=list(), loss_cbs=list(), eval_cbs=list(), sample_cbs=list(),
             use_exemplars=True, add_exemplars=False, eval_cbs_exemplars=list(), savepath='./'):
    '''Train a model (with a "train_a_batch" method) on multiple tasks, with replay-strategy specified by [replay_mode].

    [model]             <nn.Module> main model to optimize across all tasks
    [train_datasets]    <list> with for each task the training <DataSet>
    [replay_mode]       <str>, choice from "generative", "exact", "current", "offline" and "none"
    [scenario]          "domain"
    [classes_per_task]  <int>, # of classes per task
    [iters]             <int>, # of optimization-steps (i.e., # of batches) per task
    [generator]         None or <nn.Module>, if a seperate generative model should be trained (for [gen_iters] per task)
    [*_cbs]             <list> of call-back functions to evaluate training-progress'''


    # Set model in training-mode
    model.train()

    # Use cuda?
    cuda = model._is_on_cuda()
    device = model._device()

    # Initiate possible sources for replay (no replay for 1st task)
    Exact = Generative = Current = False
    previous_model = None

    # Register starting param-values (needed for "intelligent synapses").
    if isinstance(model, ContinualLearner) and (model.si_c>0):
        for n, p in model.named_parameters():
            if p.requires_grad:
                n = n.replace('.', '__')
                model.register_buffer('{}_SI_prev_task'.format(n), p.data.clone())

    # Loop over all tasks.
    for task, train_dataset in enumerate(train_datasets, 1):
        # If offline replay-setting, create large database of all tasks so far
        if replay_mode == "offline":
            train_dataset = ConcatDataset(train_datasets[:task])

        # Add exemplars (if available) to current dataset (if requested)
        if add_exemplars and task>1:
            # ---------- ADHOC SOLUTION: permMNIST needs transform to tensor, while splitMNIST does not ---------- #
            if len(train_datasets)>6:
                target_transform = (lambda y, x=classes_per_task: torch.tensor(y%x)) if (
                        scenario=="domain"
                ) else (lambda y: torch.tensor(y))
            else:
                target_transform = (lambda y, x=classes_per_task: y%x) if scenario=="domain" else None
            # ---------------------------------------------------------------------------------------------------- #
            exemplar_dataset = ExemplarDataset(model.exemplar_sets, target_transform=target_transform)
            training_dataset = ConcatDataset([train_dataset, exemplar_dataset])
        else:
            training_dataset = train_dataset

        # Prepare <dicts> to store running importance estimates and param-values before update ("Synaptic Intelligence")
        if isinstance(model, ContinualLearner) and (model.si_c > 0):
            W = {}
            p_old = {}
            for n, p in model.named_parameters():
                if p.requires_grad:
                    n = n.replace('.', '__')
                    W[n] = p.data.clone().zero_()
                    p_old[n] = p.data.clone()

        # Find [active_classes]
        active_classes = None  # -> for Domain-IL scenario, always all classes are active


        # Reset state of optimizer(s) for every task (if requested)
        if model.optim_type=="adam_reset":
            model.optimizer = optim.Adam(model.optim_list, betas=(0.9, 0.999))
        if (generator is not None) and generator.optim_type=="adam_reset":
            generator.optimizer = optim.Adam(model.optim_list, betas=(0.9, 0.999))

        # Initialize # iters left on current data-loader(s)
        iters_left = iters_left_previous = 1

        # Define tqdm progress bar(s)
        progress = tqdm.tqdm(range(1, iters+1))
        if generator is not None:
            progress_gen = tqdm.tqdm(range(1, gen_iters+1))

        # Loop over all iterations
        iters_to_use = iters if (generator is None) else max(iters, gen_iters)
        for batch_index in range(1, iters_to_use+1):

            # Update # iters left on current data-loader(s) and, if needed, create new one(s)
            iters_left -= 1
            if iters_left==0:
                data_loader = iter(utils.get_data_loader(training_dataset, batch_size, cuda=cuda, drop_last=True))
                # NOTE:  [train_dataset]  is training-set of current task
                #      [training_dataset] is training-set of current task with stored exemplars added (if requested)
                iters_left = len(data_loader)
            if Exact:
                iters_left_previous -= 1
                if iters_left_previous==0:
                    batch_size_to_use = min(batch_size, len(ConcatDataset(previous_datasets)))
                    data_loader_previous = iter(utils.get_data_loader(ConcatDataset(previous_datasets),
                                                                      batch_size_to_use, cuda=cuda, drop_last=True))
                    iters_left_previous = len(data_loader_previous)


            # -----------------Collect data------------------#

            #####-----CURRENT BATCH-----#####
            x, y = next(data_loader)                                    #--> sample training data of current task
            x, y = x.to(device), y.to(device)                           #--> transfer them to correct device

            scores = None

            #####-----REPLAYED BATCH-----#####
            if not Exact and not Generative and not Current:
                x_ = y_ = scores_ = None   #-> if no replay

            ##-->> Exact Replay <<--##
            if Exact:
                scores_ = None

                # Sample replayed training data, move to correct device
                x_, y_ = next(data_loader_previous)
                x_ = x_.to(device)
                y_ = y_.to(device) if (model.replay_targets=="hard") else None
                # If required, get target scores (i.e, [scores_]         -- using previous model, with no_grad()
                if (model.replay_targets=="soft"):
                    with torch.no_grad():
                        scores_ = previous_model(x_)
                    scores_ = scores_


            ##-->> Generative / Current Replay <<--##
            if Generative or Current:
                # Get replayed data (i.e., [x_]) -- either current data or use previous generator
                x_ = x if Current else previous_generator.sample(batch_size)

                # Get target scores and labels (i.e., [scores_] / [y_]) -- using previous model, with no_grad()
                # -if there are no task-specific mask, obtain all predicted scores at once
                if (not hasattr(previous_model, "mask_dict")) or (previous_model.mask_dict is None):
                    with torch.no_grad():
                        all_scores_ = previous_model(x_)
                # -depending on chosen scenario, collect relevant predicted scores (per task, if required)
                if scenario in ("domain") and (
                        (not hasattr(previous_model, "mask_dict")) or (previous_model.mask_dict is None)
                ):
                    scores_ = all_scores_
                    _, y_ = torch.max(scores_, dim=1)
                else:
                    # NOTE: it's possible to have scenario=domain with task-mask (so actually it's the Task-IL scenario)
                    # -[x_] needs to be evaluated according to each previous task, so make list with entry per task
                    scores_ = list()
                    y_ = list()
                    for task_id in range(task - 1):
                        # -if there is a task-mask (i.e., XdG is used), obtain predicted scores for each task separately
                        if hasattr(previous_model, "mask_dict") and previous_model.mask_dict is not None:
                            previous_model.apply_XdGmask(task=task_id + 1)
                            with torch.no_grad():
                                all_scores_ = previous_model(x_)
                        temp_scores_ = all_scores_

                        _, temp_y_ = torch.max(temp_scores_, dim=1)
                        scores_.append(temp_scores_)
                        y_.append(temp_y_)

                # Only keep predicted y/scores if required (as otherwise unnecessary computations will be done)
                y_ = y_ if (model.replay_targets == "hard") else None
                scores_ = scores_ if (model.replay_targets == "soft") else None


            #---> Train MAIN MODEL
            if batch_index <= iters:

                # Train the main model with this batch
                loss_dict = model.train_a_batch(x, y, x_=x_, y_=y_, scores=scores, scores_=scores_,
                                                active_classes=active_classes, task=task, rnt = 1./task)

                # Update running parameter importance estimates in W
                if isinstance(model, ContinualLearner) and (model.si_c>0):
                    for n, p in model.named_parameters():
                        if p.requires_grad:
                            n = n.replace('.', '__')
                            if p.grad is not None:
                                W[n].add_(-p.grad*(p.detach()-p_old[n]))
                            p_old[n] = p.detach().clone()

                # Fire callbacks (for visualization of training-progress / evaluating performance after each task)
                for loss_cb in loss_cbs:
                    if loss_cb is not None:
                        loss_cb(progress, batch_index, loss_dict, task=task)
                for eval_cb in eval_cbs:
                    if eval_cb is not None:
                        eval_cb(model, batch_index, task=task)
                if model.label == "VAE":
                    for sample_cb in sample_cbs:
                        if sample_cb is not None:
                            sample_cb(model, batch_index, task=task)


            #---> Train GENERATOR
            if generator is not None and batch_index <= gen_iters:
                # Train the generator with this batch
                loss_dict = generator.train_a_batch(x, y, x_=x_, y_=y_, scores_=scores_, active_classes=active_classes,
                                                    task=task, rnt=1./task)

                # Fire callbacks on each iteration
                for loss_cb in gen_loss_cbs:
                    if loss_cb is not None:
                        loss_cb(progress_gen, batch_index, loss_dict, task=task)
                for sample_cb in sample_cbs:
                    if sample_cb is not None:
                        sample_cb(generator, batch_index, task=task)


        ##----------> UPON FINISHING EACH TASK...

        # Close progres-bar(s)
        progress.close()
        if generator is not None:
            progress_gen.close()

        # EWC: estimate Fisher Information matrix (FIM) and update term for quadratic penalty
        if isinstance(model, ContinualLearner) and (model.ewc_lambda>0):
            # -find allowed classes
            allowed_classes = None
            # -if needed, apply correct task-specific mask
            if model.mask_dict is not None:
                model.apply_XdGmask(task=task)
            # -estimate FI-matrix
            model.estimate_fisher(training_dataset, allowed_classes=allowed_classes)

        # SI: calculate and update the normalized path integral
        if isinstance(model, ContinualLearner) and (model.si_c>0):
            model.update_omega(W, model.epsilon)

        # EXEMPLARS: update exemplar sets
        if (add_exemplars or use_exemplars) or replay_mode=="exemplars":
            exemplars_per_class = int(np.floor(model.memory_budget / (classes_per_task*task)))
            # reduce examplar-sets
            model.reduce_exemplar_sets(exemplars_per_class)
            # for each new class trained on, construct examplar-set
            new_classes = list(range(classes_per_task))
            for class_id in new_classes:
                start = time.time()
                # create new dataset containing only all examples of this class
                class_dataset = SubDataset(original_dataset=train_dataset, sub_labels=[class_id])
                # based on this dataset, construct new exemplar-set for this class
                model.construct_exemplar_set(dataset=class_dataset, n=exemplars_per_class)
                print("Constructed exemplar-set for class {}: {} seconds".format(class_id, round(time.time()-start)))
            model.compute_means = True
            # evaluate this way of classifying on test set
            for eval_cb in eval_cbs_exemplars:
                if eval_cb is not None:
                    eval_cb(model, iters, task=task)

        # REPLAY: update source for replay
        previous_model = copy.deepcopy(model).eval()
        if replay_mode == 'generative':
            Generative = True
            previous_generator = copy.deepcopy(generator).eval() if generator is not None else previous_model
        elif replay_mode == 'current':
            Current = True
        elif replay_mode in ('exemplars', 'exact'):
            Exact = True
            if replay_mode == "exact":
                previous_datasets = train_datasets[:task]
            else:
                target_transform = (lambda y, x=classes_per_task: y % x)
                previous_datasets = [
                    ExemplarDataset(model.exemplar_sets, target_transform=target_transform)]

        precs = [evaluate.validate(
            model, test_datasets[i], verbose=False, test_size=None, task=i + 1, with_exemplars=False,
            allowed_classes= None
        ) for i in range(len(test_datasets))]
        output.append(precs)

        precs5 = [evaluate.validate5(
            model, test_datasets[i], verbose=False, test_size=None, task=i + 1, with_exemplars=False,
            allowed_classes=None
        ) for i in range(len(test_datasets))]
        output5.append(precs5)

    os.makedirs(savepath+'/top5',exist_ok=True)
    savepath1=savepath+'/'+str(datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S'))+'.csv'
    f = open(savepath1, 'w')
    writer=csv.writer(f)    
    writer.writerows(output)        
    f.close()
    savepath5=savepath+'/top5/'+str(datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S'))+'.csv'
    f = open(savepath5, 'w')
    writer=csv.writer(f)    
    writer.writerows(output5)        
    f.close()
    print(savepath)


