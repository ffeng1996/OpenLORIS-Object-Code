# Continual Learning
This is the implementation of the following paper: 
[OpenLORIS-Object: A Dataset and Benchmark towardsLifelong Object Recognition](https://arxiv.org/pdf/1911.06487.pdf)


## Requirements
The current version of the code has been tested with:
* `pytorch 0.4.1`
* `torchvision 0.2.1`
* `tqdm`
* `visdom`

## Data preparation
Download data from Google Drive and Baidu Pan. Run `python benchmark1.py` `python benchmark2.py` and then copy the generated folders to `./img`.
Run `python pk_gene.py` to generate the `.pkl` files of data.

## Running the benchmark 1
Individual experiments can be run with `factor.py`. Main option is:
- `python3 factor.py --factor`: which kind of experiment? (`clutter`|`illumination`|`occlusion`|`pixel`)

## Running the benchmark 2
The main option to run benchmark2 is:
- `python3 factor.py --factor=sequence`

To run specific methods, use the following:
- Context-dependent-Gating (XdG): `./factor.py --xdg=0.8 --savepath=xdg`
- Elastic weight consolidation (EWC): `./factor.py --ewc --lambda=5000 --savepath=ewc`
- Online EWC:  `./factor.py --ewc --online --lambda=5000 --gamma=1 --savepath=ewconline`
- Synaptic intelligenc (SI): `./factor.py --si --c=0.1 --savepath=si`
- Learning without Forgetting (LwF): `./factor.py --replay=current --distill --savepath=lwf`
- Deep Generative Replay (DGR): `./factor.py --replay=generative --savepath=dgr`
- DGR with distillation: `./factor.py --replay=generative --distill --savepath=distilldgr`
- Replay-trough-Feedback (RtF): `./factor.py --replay=generative --distill --feedback --savepath=rtf`
- Culmulative: `./factor.py --culmulative=1 --savepath=culmulative`
- Naive: `./factor.py --savepath=naive`

For information on further options: `./factor.py -h`.

## Repository Structure
```
OpenLORISCode 
├── img
├── lib
│   ├── callbacks.py
│   ├── continual_learner.py
│   ├── encoder.py
│   ├── exemplars.py
│   ├── replayer.py
│   ├── train.py
│   ├── vae_models.py
│   ├── visual_plt.py
├── _compare.py
├── _compare_replay.py
├── _compare_taskID.py
├── data.py
├── evaluate.py
├── excitability_modules.py
├── factor.py
├── linear_nets.py
├── param_stamp.py
├── pk_gene.py
├── visual_visdom.py
├── utils.py
└── README.md
```
## Citation 
Please consider citing our papers if you use this code in your research:
```
@misc{1911.06487,
  Author = {Qi She and Fan Feng and Xinyue Hao and Qihan Yang and Chuanlin Lan and Vincenzo Lomonaco and Xuesong Shi and Zhengwei Wang and Yao Guo and Yimin Zhang and Fei Qiao and Rosa H. M. Chan},
  Title = {OpenLORIS-Object: A Dataset and Benchmark towards Lifelong Object Recognition},
  Year = {2019},
  Eprint = {arXiv:1911.06487},
}
```

## Acknowledgements
Parts of code were borrowed from [here](https://github.com/GMvandeVen/continual-learning).



## Issue / Want to Contribute ? 
Open a new issue or do a pull request incase you are facing any difficulty with the code base or if you want to contribute to it.


