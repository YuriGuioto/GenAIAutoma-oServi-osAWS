.PHONY: check up etapa2 etapa3 etapa4 etapa5 etapa6 integrador agente-integrador

check:
	@aws sts get-caller-identity

up:
	docker compose up -d
	docker compose exec ollama ollama pull llama3.2

etapa2:
	./scripts/recursos-partida.sh
	python3 scripts/inventario.py
	./scripts/testar-menor-privilegio.sh

etapa3:
	cfn-lint infra/vpc.yaml
	aws ssm put-parameter --name "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64" --type "String" --value "ami-0al2023floci00001" --overwrite
	aws cloudformation deploy --template-file infra/vpc.yaml --stack-name lab-ia
	aws cloudformation describe-stack-resources --stack-name lab-ia --output table

etapa4:
	./scripts/implantar-etapa4.sh
	./scripts/testar-etapa4.sh

etapa5:
	./scripts/montar-cenario-etapa5.sh
	python3 scripts/publicar-metricas-cpu.py
	python3 src/agente/agente.py

etapa6:
	python3 src/governanca/classificador_regras.py
	python3 scripts/analisar-custos-etapa6.py
	python3 scripts/testar-injection.py
	./scripts/aplicar-iam-minimo-lambda.sh

integrador:
	./scripts/subir-tudo.sh

agente-integrador:
	python3 src/integrador/agente_irrigacao.py
