FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    git curl gnupg nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# install playwright MCP
RUN npm install -g @playwright/mcp@latest

# install chromium with all deps into known path
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN npx -y playwright@latest install --with-deps chromium

# pin executable path for MCP server to find it
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/ms-playwright/chromium-*/chrome-linux/chrome

COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip install git+https://github.com/sanjaymk908/trukyc-adk.git@main#subdirectory=truclaw_adk_final

COPY . .
RUN truclaw install && python3 -c "import truclaw_adk.autopatch; print('autopatch OK')"

EXPOSE 8080
CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8080", "."]
