.PHONY: start start-light start-heavy start-vision stop status

# One-command start (roadmap Phase 1.6) -- see start.sh for what each step
# checks and why. `make start` is the default `full` mode.
start:
	./start.sh full

start-light:
	./start.sh light

start-heavy:
	./start.sh heavy

start-vision:
	./start.sh full --vision

stop:
	docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml down

status:
	docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml ps
