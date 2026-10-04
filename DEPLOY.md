# Despliegue en la VPS con HestiaCP

Resultado final: `https://isc.jnhtn.com.mx` servido por HestiaCP (dominio + SSL) que reenvía todo a FastAPI en `127.0.0.1:8010`, que a su vez usa Ollama en `127.0.0.1:11434`.

```
Navegador ──HTTPS──► Nginx (HestiaCP, plantilla "brujula") ──► FastAPI :8010 (PM2) ──► Ollama :11434
```

> **¿Hay que "hacer la web" en Hestia?** Sí, pero sólo para registrar el dominio y obtener el certificado SSL. **No se sube nada a `public_html`**: la plantilla `brujula` hace que Nginx mande todas las peticiones a FastAPI, que es quien sirve la página. Tampoco se toca `/etc/nginx/sites-available`, porque Hestia regenera la configuración de Nginx y borraría los cambios manuales.

---

## Paso 0. Verificar el DNS

En tu computadora:

```bash
nslookup isc.jnhtn.com.mx
```

Debe responder con la IP de la VPS. Si usas Cloudflare, deja el registro en **"DNS only"** (nube gris) mientras se emite el certificado.

## Paso 1. Subir el código a GitHub

La entrega pide el código o su URL, y además así es más fácil actualizar la VPS.

```bash
cd brujula-isc
git init
git add .
git commit -m "Brújula ISC: agente conversacional de la carrera"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/brujula-isc.git
git push -u origin main
```

(Crea antes el repositorio vacío `brujula-isc` en GitHub. `.env` y `venv/` ya están en `.gitignore`.)

## Paso 2. Clonar en la VPS

Entra por SSH **con el mismo usuario que corre PM2 para tu bot de Discord** (revísalo con `pm2 ls`; si el bot aparece ahí, ese es el usuario correcto).

```bash
ssh root@IP_DE_LA_VPS
sudo git clone https://github.com/TU_USUARIO/brujula-isc.git /opt/brujula-isc
sudo chown -R $USER:$USER /opt/brujula-isc
cd /opt/brujula-isc
```

Se pone en `/opt` y no dentro de `/home/<usuario>/web/...` para que el código y los datos no queden expuestos como archivos públicos.

## Paso 3. Instalar Ollama, el modelo y la app

```bash
bash deploy/setup.sh
```

El script:

1. Instala Ollama (si no está) como servicio de systemd y descarga `qwen2.5:7b` (~4.7 GB, tarda unos minutos).
2. Crea el entorno virtual `venv/` e instala FastAPI, Uvicorn, httpx y python-dotenv.
3. Crea `.env` a partir de `.env.example`.
4. Arranca la app con PM2 (`brujula-isc`) en `127.0.0.1:8010` y hace `pm2 save`.
5. Prueba `/api/health`. Debe salir algo como:
   `{"ok":true,"modelo":"qwen2.5:7b","modelo_descargado":true}`

Comprobaciones:

```bash
pm2 ls                          # brujula-isc en "online", junto a tu bot
ollama list                     # aparece qwen2.5:7b
ss -tlnp | grep -E "8010|11434" # ambos deben escuchar en 127.0.0.1, NO en 0.0.0.0
```

Prueba real del agente, todavía sin dominio:

```bash
curl -s -X POST http://127.0.0.1:8010/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"¿Qué materias hay en 8.º semestre?"}]}' | python3 -m json.tool
```

En `herramientas` debe aparecer `consultar_reticula`. La primera respuesta tarda más porque el modelo se carga en RAM; después se queda cargado (`OLLAMA_KEEP_ALIVE=-1`).

Si `pm2` no arrancó al reiniciar la VPS en el pasado, ejecuta una vez `pm2 startup` y sigue la instrucción que imprime (probablemente ya lo hiciste para el bot).

## Paso 4. Crear el dominio en HestiaCP

1. Entra al panel: `https://IP_DE_LA_VPS:8083` (o la URL que uses).
2. Ve a la pestaña **Web** → **Add Web Domain**.
3. Domain: `isc.jnhtn.com.mx`.
4. Desmarca **Create DNS zone** si tu DNS lo administras fuera de Hestia (por ejemplo en el panel de Hostinger). Si tus nameservers apuntan a Hestia, déjalo marcado.
5. Desmarca **Enable mail for this domain**.
6. Abre **Advanced Options** y marca:
   - **Enable SSL for this domain**
   - **Use Let's Encrypt to obtain SSL certificate**
   - **Enable automatic HTTPS redirection**
   - (opcional) **Enable HTTP Strict Transport Security (HSTS)**
7. **Save**. Hestia crea el dominio y saca el certificado. Si marca error de Let's Encrypt, el DNS todavía no propaga: espera unos minutos y vuelve a intentarlo desde *Edit → SSL*.

En este punto `https://isc.jnhtn.com.mx` muestra la página por defecto de Hestia. Es normal.

## Paso 5. Instalar y aplicar la plantilla "brujula"

```bash
cd /opt/brujula-isc
sudo bash deploy/hestia/instalar-plantillas.sh
```

El script lee `/usr/local/hestia/conf/hestia.conf` y detecta tu configuración:

- **Nginx + Apache** (lo más común): instala `brujula` como **Proxy Template**.
- **Sólo Nginx + PHP-FPM**: instala `brujula` como **Web Template (NGINX)**.

Después, en el panel: **Web** → `isc.jnhtn.com.mx` → **Edit** → **Advanced Options** y elige `brujula` en el campo que corresponda según lo que dijo el script (*Proxy Template* o *Web Template*). Luego **Save**.

Alternativa por consola (cambia `admin` por tu usuario de Hestia):

```bash
# Si el script dijo PROXY TEMPLATE:
sudo /usr/local/hestia/bin/v-change-web-domain-proxy-tpl admin isc.jnhtn.com.mx brujula
# Si el script dijo WEB TEMPLATE:
sudo /usr/local/hestia/bin/v-change-web-domain-tpl admin isc.jnhtn.com.mx brujula
```

La plantilla conserva las líneas `include .../nginx.conf_*` y `nginx.ssl.conf_*`, que Hestia usa para la redirección a HTTPS y para renovar el certificado automáticamente.

## Paso 6. Verificar

```bash
curl -I https://isc.jnhtn.com.mx            # HTTP/2 200 (o HTTP/1.1 200)
curl https://isc.jnhtn.com.mx/api/health    # {"ok":true,...}
```

Abre `https://isc.jnhtn.com.mx` en el navegador y prueba las sugerencias. También queda la documentación automática de la API en `https://isc.jnhtn.com.mx/docs`.

## Paso 7. Evidencias para la entrega

Toma capturas (o un video corto) de:

1. La pantalla inicial.
2. "¿Qué materias hay en 8.º semestre?" (se resalta la fila en la retícula).
3. "¿De qué trata Visión Artificial?" (responde con la liga al programa oficial).
4. Marcar materias en *Mi retícula* → **Calcular mi avance**.
5. "Me gustan los robots y la IA, ¿qué me conviene?".
6. El apartado desplegable "El agente…" abierto, mostrando la herramienta usada.

Guárdalas en `docs/capturas/` y súbelas al repositorio.

---

## Actualizar después de un cambio

```bash
cd /opt/brujula-isc
git pull
venv/bin/pip install -r requirements.txt   # sólo si cambió requirements.txt
pm2 restart brujula-isc
```

Los cambios en `data/` (retícula, trámites, perfiles) también requieren `pm2 restart brujula-isc`.

## Ajustes de rendimiento

- Con 8 vCPU, `qwen2.5:7b` genera aproximadamente 8 a 12 tokens por segundo: una respuesta típica tarda de 10 a 25 s. Si te parece lento, cambia en `.env` a `OLLAMA_MODEL=qwen2.5:3b` (el doble de rápido), ejecuta `ollama pull qwen2.5:3b` y `pm2 restart brujula-isc`.
- La RAM no es problema: el modelo de 7B ocupa unos 5 GB de tus 32 GB.

## Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| Sigue apareciendo la página de Hestia | La plantilla no se aplicó | Repite el paso 5 y revisa que el campo correcto diga `brujula` |
| **502 Bad Gateway** | La app no está corriendo | `pm2 logs brujula-isc` y `pm2 restart brujula-isc` |
| **504 Gateway Timeout** | El modelo tardó más de 300 s | Usa `qwen2.5:3b` o revisa la carga con `htop` |
| "El modelo no está disponible" en el chat | Ollama detenido o modelo sin descargar | `systemctl status ollama`, `ollama list`, `ollama pull qwen2.5:7b` |
| Let's Encrypt falla | DNS sin propagar o proxy de Cloudflare activo | Verifica el paso 0 y repite desde *Edit → SSL* |
| "Demasiadas preguntas en un minuto" | Límite por IP | Sube `RATE_LIMIT_PER_MIN` en `.env` y reinicia |
| El agente responde sin usar herramientas | Modelo pequeño | Usa `qwen2.5:7b`; el botón **Calcular mi avance** siempre fuerza la herramienta |

Logs útiles:

```bash
pm2 logs brujula-isc --lines 100
journalctl -u ollama -n 100
tail -f /var/log/nginx/domains/isc.jnhtn.com.mx.error.log
```

## Alternativa sin HestiaCP

En un servidor con Nginx "puro", crea un `server` con el mismo bloque `location /` que está en `deploy/hestia/brujula-web.tpl` y saca el certificado con `sudo certbot --nginx -d isc.jnhtn.com.mx`.
