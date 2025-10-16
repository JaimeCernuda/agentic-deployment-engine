# Architecture Diagrams

This directory contains rendered mermaid diagrams for multi-agent architecture patterns.

## Files

### PNG Images (Rendered)
- `01_hub_and_spoke.png` - Hub-and-Spoke (Star) pattern
- `02_pipeline.png` - Pipeline (Sequential) pattern
- `03_peer_to_peer.png` - Peer-to-Peer (Mesh) pattern
- `04_hierarchical.png` - Hierarchical (Tree) pattern
- `05_blackboard.png` - Blackboard (Shared Memory) pattern
- `06_marketplace.png` - Marketplace (Broker) pattern
- `07_event_driven.png` - Event-Driven (Pub/Sub) pattern
- `08_decision_tree.png` - Architecture selection decision tree
- `09_current_system.png` - Current clean_mcp_a2a system

### MMD Files (Source)
- `*.mmd` - Mermaid source files for each diagram

## Rendering

To re-render all diagrams:

```bash
cd /home/jcernuda/claude_agents/clean_mcp_a2a/docs/images

for file in *.mmd; do
  /home/jcernuda/.nvm/versions/node/v22.16.0/bin/mmdc -i "$file" -o "${file%.mmd}.png" -b transparent
done
```

## Customization

1. Edit `.mmd` files with your preferred text editor
2. Re-render using the command above
3. Images will be updated automatically

## Mermaid CLI Options

```bash
# Transparent background (default)
mmdc -i input.mmd -o output.png -b transparent

# White background
mmdc -i input.mmd -o output.png -b white

# Custom dimensions
mmdc -i input.mmd -o output.png -w 2000 -H 1500

# Scale 2x
mmdc -i input.mmd -o output.png -s 2

# SVG output
mmdc -i input.mmd -o output.svg
```

## Usage in Markdown

```markdown
![Hub-and-Spoke Pattern](images/01_hub_and_spoke.png)
```

## See Also

- `../ARCHITECTURE_VISUAL_INDEX.md` - Full visual guide with all diagrams
- `../ARCHITECTURE_PATTERNS_COMPARISON.md` - Detailed pattern comparison
- `../MULTI_AGENT_ARCHITECTURES.md` - Complete architecture documentation
