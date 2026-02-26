SHELL := /bin/bash

INFRA_COMPOSE := docker compose -f infra/docker-compose.yml
SUBS_COMPOSE := docker compose -f services/subscriptions/docker-compose.yml
NOTIFS_COMPOSE := docker compose -f services/notifications/docker-compose.yml
DELIVERY_COMPOSE := docker compose -f services/delivery/docker-compose.yml
BFF_COMPOSE := docker compose -f services/bff/docker-compose.yml

.PHONY: up down restart ps logs smoke test

up:
	$(INFRA_COMPOSE) up -d --build postgres redis nats auth-service
	$(SUBS_COMPOSE) up -d --build postgres subscriptions-service
	$(NOTIFS_COMPOSE) up -d --build postgres nats notifications-api notifications-outbox-publisher notifications-scheduler
	$(DELIVERY_COMPOSE) up -d --build postgres redis nats delivery-api delivery-consumer delivery-worker
	$(BFF_COMPOSE) up -d --build redis bff-gateway

down:
	$(BFF_COMPOSE) down
	$(DELIVERY_COMPOSE) down
	$(NOTIFS_COMPOSE) down
	$(SUBS_COMPOSE) down
	$(INFRA_COMPOSE) down

restart: down up

ps:
	$(INFRA_COMPOSE) ps
	$(SUBS_COMPOSE) ps
	$(NOTIFS_COMPOSE) ps
	$(DELIVERY_COMPOSE) ps
	$(BFF_COMPOSE) ps

logs:
	$(INFRA_COMPOSE) logs --tail=100 auth-service
	$(SUBS_COMPOSE) logs --tail=100 subscriptions-service
	$(NOTIFS_COMPOSE) logs --tail=100 notifications-api notifications-outbox-publisher notifications-scheduler
	$(DELIVERY_COMPOSE) logs --tail=100 delivery-api delivery-consumer delivery-worker
	$(BFF_COMPOSE) logs --tail=100 bff-gateway

smoke:
	./scripts/smoke_all.sh

test:
	source ../.venv/bin/activate && python -m pytest -q services/auth/auth_service/tests/unit services/subscriptions/subscriptions_service/tests/unit services/notifications/notifications_service/tests/unit services/delivery/delivery_service/tests/unit services/bff/bff_gateway/tests/unit
