import os


def process(data):
    result = []
    for i in range(len(data)):
        if data[i] > 0:
            result.append(data[i] * 2)
        else:
            result.append(0)
    return result


def read_file(path):
    f = open(path)
    content = f.read()
    return content


def calc(a, b, op):
    if op == "add":
        return a + b
    if op == "sub":
        return a - b
    if op == "mul":
        return a * b
    if op == "div":
        return a / b


class Config:
    def __init__(self):
        self.debug = True
        self.path = os.getcwd()
