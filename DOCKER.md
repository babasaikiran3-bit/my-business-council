# Docker Setup pentru LLM Council

Acest document conține toate instrucțiunile pentru a rula LLM Council în Docker.

## Cerințe Preliminare

- Docker instalat (versiunea 20.10 sau mai nouă)
- Docker Compose instalat (versiunea 2.0 sau mai nouă)
- Cheie API OpenRouter (obține de la https://openrouter.ai/)

## Configurare Inițială

### 1. Creează fișierul `.env`

În directorul principal al proiectului, creează un fișier `.env` cu cheia ta API:

```bash
echo "OPENROUTER_API_KEY=sk-or-v1-your-api-key-here" > .env
```

Sau creează manual fișierul `.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

**IMPORTANT**: Înlocuiește `sk-or-v1-your-api-key-here` cu cheia ta reală de la OpenRouter.

### 2. Asigură-te că există directorul pentru date

```bash
mkdir -p data/conversations
```

## Metoda 1: Rulare cu Docker Compose (Recomandat)

Aceasta este metoda cea mai simplă și recomandată.

### Build și Start

```bash
docker-compose up -d --build
```

Opțiuni:
- `-d` - rulează în background (detached mode)
- `--build` - construiește imaginea înainte de a porni

### Verifică Status

```bash
docker-compose ps
```

Ar trebui să vezi containerul `llm-council` ca `running`.

### Vizualizează Logurile

```bash
# Toate logurile
docker-compose logs -f

# Ultimele 100 de linii
docker-compose logs --tail=100 -f
```

### Stop Serviciul

```bash
docker-compose down
```

### Restart Serviciul

```bash
docker-compose restart
```

### Rebuild după modificări

Dacă faci modificări la cod:

```bash
docker-compose down
docker-compose up -d --build
```

## Metoda 2: Rulare cu Docker direct

Dacă preferi să rulezi direct cu comenzi Docker (fără Compose):

### Build Imaginea

```bash
docker build -t llm-council:latest .
```

### Rulare Container

```bash
docker run -d \
  --name llm-council \
  -p 23000:23000 \
  -e OPENROUTER_API_KEY="sk-or-v1-your-api-key-here" \
  -v "$(pwd)/data:/app/data" \
  llm-council:latest
```

### Verifică Status

```bash
docker ps | grep llm-council
```

### Vizualizează Logurile

```bash
docker logs -f llm-council
```

### Stop Container

```bash
docker stop llm-council
docker rm llm-council
```

### Restart Container

```bash
docker restart llm-council
```

## Acces la Aplicație

După ce containerul pornește, aplicația va fi disponibilă la:

**http://localhost:23000**

Deschide această adresă în browser pentru a accesa interfața LLM Council.

## Verificare Health Check

Docker include un health check automat. Verifică starea cu:

```bash
docker inspect llm-council | grep -A 10 Health
```

Sau dacă folosești Docker Compose:

```bash
docker-compose ps
```

Status-ul ar trebui să fie `healthy` după câteva secunde.

## Persistența Datelor

Conversațiile sunt salvate în directorul `./data/conversations/` pe host-ul tău.
Acest director este montat ca volum în container, deci datele vor persista chiar dacă oprești sau ștergi containerul.

## Troubleshooting

### Containerul nu pornește

1. Verifică logurile:
   ```bash
   docker-compose logs
   ```

2. Asigură-te că portul 23000 nu este deja utilizat:
   ```bash
   lsof -i :23000
   # sau
   netstat -an | grep 23000
   ```

3. Verifică că fișierul `.env` există și conține cheia API corectă

### Erori de conexiune la API

1. Verifică că `OPENROUTER_API_KEY` este setat corect:
   ```bash
   docker-compose exec llm-council env | grep OPENROUTER
   ```

2. Testează conectivitatea din container:
   ```bash
   docker-compose exec llm-council curl -I https://openrouter.ai
   ```

### Build eșuează

1. Curăță cache-ul Docker:
   ```bash
   docker builder prune -a
   ```

2. Rebuild fără cache:
   ```bash
   docker-compose build --no-cache
   ```

### Frontend nu se încarcă

1. Verifică că build-ul frontend s-a făcut corect în timpul build-ului Docker
2. Verifică logurile pentru erori:
   ```bash
   docker-compose logs | grep -i error
   ```

## Comenzi Utile

### Intră în container (debugging)

```bash
docker-compose exec llm-council /bin/bash
```

### Verifică variabilele de mediu

```bash
docker-compose exec llm-council env
```

### Verifică structura de fișiere

```bash
docker-compose exec llm-council ls -la /app
```

### Monitorizare resurse

```bash
docker stats llm-council
```

### Curăță toate datele (ATENȚIE!)

```bash
# Oprește și șterge containerul
docker-compose down

# Șterge imaginea
docker rmi llm-council:latest

# Șterge datele persistente (ATENȚIE: vei pierde toate conversațiile!)
rm -rf data/conversations/*
```

## Configurare Avansată

### Schimbă Portul

Pentru a schimba portul de la 23000 la altceva, editează `docker-compose.yml`:

```yaml
ports:
  - "8080:23000"  # Schimbă 8080 cu portul dorit pe host
```

Apoi restart:
```bash
docker-compose down
docker-compose up -d
```

### Configurează Modelele

Modelele sunt configurate în `backend/config.py`. Pentru a schimba modelele:

1. Editează `backend/config.py`
2. Rebuild imaginea:
   ```bash
   docker-compose up -d --build
   ```

### Backup Conversații

```bash
# Creează backup
tar -czf llm-council-backup-$(date +%Y%m%d).tar.gz data/

# Restore din backup
tar -xzf llm-council-backup-YYYYMMDD.tar.gz
```

## Producție

Pentru deployment în producție:

1. **Folosește HTTPS**: Pune un reverse proxy (nginx, Caddy) în fața containerului
2. **Securizează API key-ul**: Folosește Docker secrets sau un vault
3. **Monitorizare**: Adaugă logging centralizat (ELK, Loki, etc.)
4. **Backup automat**: Configurează backup-uri regulate pentru `./data/`
5. **Resource limits**: Setează limite de memorie și CPU în `docker-compose.yml`:

```yaml
services:
  llm-council:
    # ... rest of config
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Suport

Pentru probleme sau întrebări:
- Verifică logurile: `docker-compose logs -f`
- Verifică documentația OpenRouter: https://openrouter.ai/docs
- Verifică `CLAUDE.md` pentru detalii tehnice despre arhitectură

## Licență

Vezi fișierul LICENSE din proiect.
