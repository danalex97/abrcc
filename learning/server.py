from flask import Flask
from flask import request

app = Flask(__name__)


@app.route('/target_bandwidth')
def hello():
    current_bandwidth = int(request.args.get('current_bandwidth'))
    print(current_bandwidth)
    return "1"

if __name__ == '__main__':
    app.run()
