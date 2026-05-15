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

# install mcp first so we know its bundled playwright version
RUN npm install -g @playwright/mcp@latest

# install chromium using the EXACT playwright version bundled in @playwright/mcp
RUN PLAYWRIGHT_BROWSERS_PATH=/ms-playwright node -e "\
const path = require('path');\
const pw = require(path.join(require.resolve('@playwright/mcp'), '../../node_modules/playwright/package.json'));\
console.log('playwright version in mcp:', pw.version);\
" || true

RUN PLAYWRIGHT_BROWSERS_PATH=/ms-playwright npx --prefix $(npm root -g)/@playwright/mcp playwright install --with-deps chromium

COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip install git+https://github.com/sanjaymk908/trukyc-adk.git@main#subdirectory=truclaw_adk_final

COPY . .
RUN truclaw install && python3 -c "import truclaw_adk.autopatch; print('autopatch OK')"

EXPOSE 8080
CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8080", "."]
