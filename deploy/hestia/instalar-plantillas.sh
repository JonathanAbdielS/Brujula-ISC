#!/usr/bin/env bash
# Copia la plantilla "brujula" al directorio correcto según cómo esté configurado HestiaCP.
set -euo pipefail
cd "$(dirname "$0")"
CONF=/usr/local/hestia/conf/hestia.conf
PROXY=$(grep -oP "^PROXY_SYSTEM='\K[^']*" $CONF || true)
WEB=$(grep -oP "^WEB_SYSTEM='\K[^']*" $CONF || true)
echo "WEB_SYSTEM=$WEB  PROXY_SYSTEM=$PROXY"
if [ "$PROXY" = "nginx" ]; then
  DEST=/usr/local/hestia/data/templates/web/nginx
  cp brujula-proxy.tpl  $DEST/brujula.tpl
  cp brujula-proxy.stpl $DEST/brujula.stpl
  echo "Instalada como PROXY TEMPLATE 'brujula' (Nginx delante de Apache)."
elif [ "$WEB" = "nginx" ]; then
  DEST=/usr/local/hestia/data/templates/web/nginx/php-fpm
  cp brujula-web.tpl  $DEST/brujula.tpl
  cp brujula-web.stpl $DEST/brujula.stpl
  echo "Instalada como WEB TEMPLATE 'brujula' (sólo Nginx + PHP-FPM)."
else
  echo "Configuración no reconocida; revisa $CONF" >&2; exit 1
fi
chmod 644 $DEST/brujula.*
