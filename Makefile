build-chain: DockerFile.chain
	docker build -f ./DockerFile.chain -t chain_sim .

save-chain:
	docker save -o ansible/prebins/chain_sim.tar chain_sim:latest

run-chain:
	docker run -itd -v $(shell pwd)/configs:/configs -p 9000:8888 chain --cfg /configs/config.ini

build-relayer: DockerFile.relayer
	docker build -f ./DockerFile.relayer -t cross_relayer .

save-relayer:
	docker save -o ansible/prebins/cross_relayer.tar cross_relayer:latest

run-relayer:
	docker run -itd cross_relayer

test-aor:
	pytest -s tests/test_aor.py

test-nor:
	pytest -s tests/test_nor.py

test-tor:
	pytest -s tests/test_tor.py

tests: test-aor test-nor test-tor
