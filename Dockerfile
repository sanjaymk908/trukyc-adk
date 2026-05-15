FROM python:3.12-slim
WORKDIR /app

# install Node.js + chromium deps for Playwright MCP
RUN apt-get update && apt-get install -y \
    git curl \
    nodejs npm \
    chromium \
    libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# pre-install playwright mcp so npx doesn't fetch at runtime
RUN npm install -g @playwright/mcp@latest

COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip install git+https://github.com/sanjaymk908/trukyc-adk.git@main#subdirectory=truclaw_adk_final

COPY . .
RUN truclaw install && python3 -c "import truclaw_adk.autopatch; print('autopatch OK')"

EXPOSE 8080
CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8080", "."]
