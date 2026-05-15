FROM python:3.12-slim
WORKDIR /app

# base deps only
RUN apt-get update && apt-get install -y --fix-missing \
    git curl gnupg \
    && rm -rf /var/lib/apt/lists/*

# install Node.js 20 via NodeSource (cleaner than apt nodejs)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# install playwright mcp
RUN npm install -g @playwright/mcp@latest

# install chromium with all deps into known path
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PYTHONUNBUFFERED=1
RUN npx -y playwright@latest install --with-deps chromium

COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip install git+https://github.com/sanjaymk908/trukyc-adk.git@main#subdirectory=truclaw_adk_final

COPY . .
RUN truclaw install && python3 -c "import truclaw_adk.autopatch; print('autopatch OK')"

EXPOSE 8080
CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8080", "."]
