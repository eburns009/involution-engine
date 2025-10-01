# Time Resolver Development Makefile
IMAGE = time-resolver:latest

.PHONY: build run audit help clean test

build:
	docker build -f ../time-resolver.Dockerfile -t $(IMAGE) ../..

run:
	docker run --rm -p 8080:8080 -e RESOLVER_PATCH_FILE=/app/config/patches_us_pre1967.json $(IMAGE)

audit:
	python /mnt/data/time_resolver_kit/time_audit_runner.py \
	  --base-url http://localhost:8080 \
	  --input-csv /mnt/data/time_resolver_kit/time_audit_input_template.csv \
	  --out-csv /mnt/data/time_resolver_kit/time_audit_report.csv

help:
	@echo "Available targets:"
	@echo "  build  - Build Docker image"
	@echo "  run    - Run container on port 8080"
	@echo "  audit  - Run time audit against running service"
	@echo "  test   - Run validation tests"
	@echo "  clean  - Clean up containers and images"

test:
	python validate_updates.py

clean:
	docker stop $$(docker ps -q --filter ancestor=$(IMAGE)) 2>/dev/null || true
	docker rmi $(IMAGE) 2>/dev/null || true