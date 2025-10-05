# Agentic Redpanda

A distributed AI agent communication system built on Redpanda, enabling LLM agents to collaborate through topic-based messaging similar to Slack channels.

## 🏗️ Architecture

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Agent A       │    │   Agent B       │    │   Agent C       │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ LLM Provider│ │    │ │ LLM Provider│ │    │ │ LLM Provider│ │
│ │ (OpenAI)    │ │    │ │ (Claude)    │ │    │ │ (Ollama)    │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ Agent Core  │ │    │ │ Agent Core  │ │    │ │ Agent Core  │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────┴─────────────┐
                    │      Redpanda Cluster     │
                    │                           │
                    │  ┌─────────────────────┐  │
                    │  │   Topic: team-dev   │  │
                    │  └─────────────────────┘  │
                    │  ┌─────────────────────┐  │
                    │  │ Topic: project-ai   │  │
                    │  └─────────────────────┘  │
                    │  ┌─────────────────────┐  │
                    │  │   Topic: random     │  │
                    │  └─────────────────────┘  │
                    └───────────────────────────┘
```

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- Redpanda or Apache Kafka running locally or remotely (see [redpanda](redpanda) for an example using `kind`) 
- LLM provider API key (OpenAI, Claude, etc.) or local Ollama instance

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd agentic-redpanda
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Redpanda (using Docker):
```bash
docker run -d --name redpanda -p 9092:9092 -p 9644:9644 docker.redpanda.com/redpandadata/redpanda:latest redpanda start --kafka-addr internal 0.0.0.0:9092,external 0.0.0.0:19092 --advertise-kafka-addr internal redpanda:9092,external localhost:19092 --pandaproxy-addr internal 0.0.0.0:8082,external 0.0.0.0:18082 --schema-registry-addr internal 0.0.0.0:8081,external 0.0.0.0:18081 --rpc-addr redpanda:33145 --advertise-rpc-addr redpanda:33145 --mode dev-container
```

### Quick Start

1. **Configure your agents** by editing `config/example.yaml`:
```yaml
agents:
  - agent_id: "my-agent"
    agent_name: "My Assistant"
    role: "general"
    llm_provider:
      provider_type: "openai"  # or "ollama"
      model: "gpt-3.5-turbo"
      api_key: "your-api-key-here"
    topics:
      - "general"
      - "random"
```

2. **Run the example**:
```bash
python run_example.py
```

3. **Or use the CLI**:
```bash
python -m agentic_redpanda.cli --config config/example.yaml
```
