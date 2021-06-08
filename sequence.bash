python3 main.py --factor=sequence --ewc --savepath='./results/sequence/ewc/'
python3 main.py --factor=sequence --ewc --online --savepath='./results/sequence/ewc_online/'
python3 main.py --factor=sequence --savepath='./results/sequence/naive/'
python3 main.py --factor=sequence --si --savepath='./results/sequence/si/'
python3 main.py --factor=sequence --cumulative=1 --savepath='./results/sequence/cumulative/'
python3 main.py --factor=sequence --replay=current --savepath='./results/sequence/lwf/'
python3 main.py --factor=sequence --replay=generative --distill --savepath='./results/sequence/dgr_distill/'
python3 main.py --factor=sequence --replay=generative --savepath='./results/sequence/dgr/'
python3 main.py --factor=sequence --replay=generative --distill --feedback --savepath='./results/sequence/dgr_distill_feedback/'