P4C ?= p4c
P4_PROGRAM ?= basic.p4
BUILD_DIR ?= build
LOG_DIR ?= logs
PCAP_DIR ?= pcaps

.PHONY: all compile run clean

all: compile

compile:
	mkdir -p $(BUILD_DIR) $(LOG_DIR) $(PCAP_DIR)
	$(P4C) --target bmv2 --arch v1model --std p4-16 \
		$(P4_PROGRAM) -o $(BUILD_DIR)

run: compile
	python3 run_mininet.py \
		--switch-json $(BUILD_DIR)/basic.json \
		--commands commands.txt \
		--log-dir $(LOG_DIR)

clean:
	rm -rf $(BUILD_DIR) $(LOG_DIR) $(PCAP_DIR)
	mn -c >/dev/null 2>&1 || true
