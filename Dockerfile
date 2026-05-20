FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --fix-missing \
    git curl gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PYTHONUNBUFFERED=1

# install mcp first
RUN npm install -g @playwright/mcp@latest

# install chrome using the playwright bundled INSIDE @playwright/mcp
RUN PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    node /usr/lib/node_modules/@playwright/mcp/node_modules/playwright/cli.js \
    install --with-deps chrome

# install PortEden for emails
# install porteden CLI
RUN curl -fsSL https://github.com/porteden/cli/releases/download/v0.2.1/porteden_0.2.1_linux_amd64.tar.gz \
    -o /tmp/porteden.tar.gz \
    && tar -xzf /tmp/porteden.tar.gz -C /usr/local/bin porteden \
    && chmod +x /usr/local/bin/porteden \
    && rm /tmp/porteden.tar.gz

COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip install git+https://github.com/sanjaymk908/trukyc-adk.git@main#subdirectory=truclaw_adk_final
RUN python3 -m playwright install --with-deps chromium

COPY . .
RUN truclaw install && python3 -c "import truclaw_adk.autopatch; print('autopatch OK')"

EXPOSE 8080
CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8080", "."]
