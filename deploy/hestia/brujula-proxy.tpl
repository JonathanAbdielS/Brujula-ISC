# Plantilla HestiaCP (HTTP) -> FastAPI en 127.0.0.1:8010
server {
    listen      %ip%:%proxy_port%;
    server_name %domain_idn% %alias_idn%;

    include %home%/%user%/conf/web/%domain%/nginx.forcessl.conf*;

    location ~ /\.(?!well-known\/) {
        deny all;
        return 404;
    }

    location / {
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # el modelo corre en CPU: hay que darle tiempo
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    include %home%/%user%/conf/web/%domain%/nginx.conf_*;
}
