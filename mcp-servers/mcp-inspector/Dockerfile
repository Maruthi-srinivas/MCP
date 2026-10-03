FROM node:22-bookworm-slim

# Installed at image build so the host does not need Node or npm.
RUN npm install -g @modelcontextprotocol/inspector@2.9.0

ENV HOST=0.0.0.0 \
    DANGEROUSLY_BIND_ALL_INTERFACES=true \
    CLIENT_PORT=6274 \
    MCP_AUTO_OPEN_ENABLED=false

EXPOSE 6274

ENTRYPOINT ["mcp-inspector"]
CMD ["--web"]
