FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && python -c "import aiogram; print('AIROGRAM_OK', aiogram.__version__)"

COPY . .

CMD ["python", "bot.py"]
