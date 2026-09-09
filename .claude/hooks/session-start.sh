#!/bin/bash
# Ставит то, без чего не работает подготовка сайтов:
#   Pillow         — обработка фотографий (кроп, замазывание номеров, цветокоррекция)
#   playwright-core — проверки готовых страниц (переполнение, битые фото, 152-ФЗ)
# Chromium в образе уже есть: /opt/pw-browsers/chromium, скачивать его не нужно.
set -euo pipefail

# Только в облачных сессиях: на локальной машине окружение настраивает сам разработчик.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

if ! python3 -c "import PIL" >/dev/null 2>&1; then
  python3 -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt
fi

if ! node -e "require.resolve('playwright-core')" >/dev/null 2>&1; then
  npm install --silent --no-audit --no-fund
fi

# Чтобы Playwright не пытался качать свой браузер.
{
  echo 'export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers'
  echo 'export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1'
} >> "${CLAUDE_ENV_FILE:-/dev/null}"

python3 -c "import PIL, sys; sys.stderr.write('Pillow %s\n' % PIL.__version__)"
node -e "console.error('playwright-core ' + require('playwright-core/package.json').version)"
