# Experiment

## Setup

**Fixed (floating within threshold):**
- Parachain block interval
- Parachain block size
- Transaction sending frequency
- Transaction sending amount

**Random:**
- Cross-chain transaction destination chain

**Statistics:**
- TPS
  - System TPS
  - Relay chain TPS
  - Parachain TPS
- Latency
  - Cross-chain transaction average latency
  - Cross-chain transaction stage latency (especially parachain latency)
- Consider
  - Relay chain storage (ledger data + storage data)
  - Parachain storage (ledger data + storage data)


## Notes

First execute, then determine the consensus process time based on the number of transactions, and finally input into the cross-chain simulator.

> NOTE: When deploying, it is important to ensure that the time difference between master and worker is sufficiently small. If this difference reaches the second level, the final measurement results will be very unstable. This is because the transaction's `init` timestamp is set on the master machine, while other timestamps are set on the `worker` machines. If the time difference between master and worker is relatively large, the final measurement results will be very unstable.
