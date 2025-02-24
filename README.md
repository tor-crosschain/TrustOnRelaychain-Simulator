# A cross-chain simulator for evaluating the performance of ToR

## Introduction

The cross-chain simulator consists of two parts: chain simulator + relayer.

**Chain Simulator**. In a cross-chain system, a single blockchain primarily contributes latency and local throughput to the entire cross-chain system. Therefore, in the cross-chain simulator, a single blockchain can be simulated using an independent process. In this project, a single blockchain is not a fully functional real blockchain but simulates core functions closely related to the cross-chain system. These include transaction pool, packaging, consensus (simulated using different strategies such as fixed time, fixed transaction number, etc.), contract execution, data persistence, and API services (sending transactions, querying on-chain information such as blocks, transactions, proofs, etc.).

**Relayer**. In a cross-chain system, the relayer is responsible for data transmission between chains (block header data, cross-chain data, and proofs, etc.). It is the key component for achieving interoperability between two blockchains and is the smallest connection unit in the cross-chain network topology. In the project, the relayer functionality is truly implemented and has strong versatility (it can connect to the currently implemented chain simulator or real blockchains, just by implementing the corresponding SDK).

## Environment Setup

This project uses `pipenv` as the environment management tool, and requires pre-installation of python-3.8.10.

```bash
# Install pyenv software
pip install pipenv

# Enter the pipenv environment

pipenv shell --python <path of python-3.8.10>

# Install dependencies
pipenv install
```

## Local Execution

The program files are in the `locals_unix/` folder, and the configuration can be passed in through the command line, such as `CHAINNUM`, `XTXNUM`, `BASE_PORT`, etc.

The parameters that can be passed in are in the `utils/localtools.py::get_args()` function, and the main indicators related to the experiment are:

```bash
--ccmode='ToR' # 3 modes, 'ToR', 'NoR', 'AoR'
--txnum=10 # the number of transactions sent to each parallel chain (normal transactions + cross-chain transactions)
--xtxratio=1.0 # the ratio of cross-chain transactions sent to each parallel chain, so the number of cross-chain transactions is txnum*xtxratio
--chainnum=100 # the number of parallel chains
```

```bash
# Execute the program directly
python locals_unix/evaluate.py --ccmode='ToR'

# Execute the program in the background
nohup python locals_unix/evaluate.py --ccmode='ToR' --txnum=500 --xtxratio=1.0 --chainnum=100 2>&1 >temp/evaluate.log &
```
After the program execution is complete, the evaluation results will be saved in a file, which is stored in the `locals_unix/output/indicates` folder with the file name `{ccmode}-{chainnum}-{txnum}-{int(xtxratio*100)}`; the `locals_unix/output/workloads` file contains the workload of each chain (the workload value is obtained every second).


<!-- ## Remote Multi-Machine Deployment

Multi-machine deployment requires docker and ansible.

The parallel chain configuration is in `ansible/configs/parachain`

The relay chain configuration is in `ansible/configs/interchain`

### Docker Image Build

```bash
# Build crosschain-simulator
make build-chain
make save-chain

# Build relayer
make build-relayer
make save-relayer
```

### Deploy through ansible

```bash
# Switch to the ansible directory
cd ansible

# If the chain and relayer images are modified
# Then set the images -> reload parameter to true in ansible/vars/main.yml
# So that ansible will deploy the latest image package to the remote server

# Deploy blockchain
ansible-playbook -f 10 deploy_relayer.yml -i inventory.yml -e ccmode=ToR
# -f: number of processes
# deploy_relayer.yml: task orchestration file
# inventory.yml: host file
# ccmode: cross-chain mode ToR NoR AoR

# Deploy gateway
ansible-playbook -f 10 deploy_relayer.yml -i inventory.yml -e ccmode=ToR
```

## Optimization -->