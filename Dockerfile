FROM python:3.10-slim

# 安装 Chrome
RUN apt-get update && \
    apt-get install -y wget unzip gnupg curl fonts-liberation libnss3 libatk1.0-0 libxss1 libappindicator1 libasound2 libgbm1 libgtk-3-0 && \
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb || apt-get -f install -y && \
    rm google-chrome-stable_current_amd64.deb

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目
COPY . .

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 启动脚本
CMD ["python", "main.py"]
