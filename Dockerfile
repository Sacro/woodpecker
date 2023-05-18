FROM nikolaik/python-nodejs
USER pn
WORKDIR /home/pn/app
COPY --chown=pn:pn pyproject.toml requirements.txt setup.py ./
RUN pip install -r requirements.txt
COPY --chown=pn:pn . ./
RUN ./run.sh
