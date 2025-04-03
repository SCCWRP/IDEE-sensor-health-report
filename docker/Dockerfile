FROM debian:latest

# Dependencies
RUN apt-get update && \
    apt-get install -y software-properties-common python3 python3-pip libpq-dev libssl-dev libcurl4-openssl-dev \
                       postgresql postgresql-contrib wget unzip gfortran libnss3-dev libgdk-pixbuf2.0-dev libgtk-3-dev libxss-dev \
                       curl xvfb libxi6 libgconf-2-4 git && \
    apt-get clean

# Initial Python packages
RUN pip3 install ipython pandas pyarrow fastparquet 'sqlalchemy<2.0' wget psycopg2 requests selenium

# Chrome
RUN curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get -y install google-chrome-stable && \
    apt-get clean

# Chrome Driver
RUN wget https://storage.googleapis.com/chrome-for-testing-public/126.0.6478.55/linux64/chromedriver-linux64.zip
RUN unzip chromedriver-linux64.zip
RUN mv chromedriver-linux64/chromedriver /usr/local/share/chromedriver
RUN ln -s /usr/local/share/chromedriver /usr/bin/chromedriver
RUN chown root:root /usr/bin/chromedriver
RUN chmod +x /usr/bin/chromedriver
RUN rm chromedriver-linux64.zip

# Admin stuff
RUN mkdir -p /var/www/IDEE/
WORKDIR /var/www/IDEE/

# Extra packages
RUN pip3 install openpyxl
RUN pip3 install fpdf
RUN pip3 install matplotlib
