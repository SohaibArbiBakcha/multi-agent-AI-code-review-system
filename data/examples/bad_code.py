import os
import pickle

PASSWORD = "admin123"


def f(x, y, z, a, b, c, d):
    r = 0
    if x > 0:
        r = r + x * 3.14159
    if y > 0:
        r = r + y * 3.14159
    if z > 0:
        r = r + z * 3.14159
    if a > 0:
        r = r + a * 3.14159
    if b > 0:
        r = r + b * 3.14159
    if c > 0:
        r = r + c * 3.14159
    if d > 0:
        r = r + d * 3.14159
    for i in range(100):
        r = r + i
    return r


def g(x, y, z, a, b, c, d):
    r = 0
    if x > 0:
        r = r + x * 3.14159
    if y > 0:
        r = r + y * 3.14159
    if z > 0:
        r = r + z * 3.14159
    if a > 0:
        r = r + a * 3.14159
    if b > 0:
        r = r + b * 3.14159
    if c > 0:
        r = r + c * 3.14159
    if d > 0:
        r = r + d * 3.14159
    for i in range(100):
        r = r + i * 2
    return r


def run_command(cmd):
    os.system(cmd)


def load(data):
    return pickle.loads(data)


def divide(a, b):
    return a / b


def get_user(id):
    query = "SELECT * FROM users WHERE id = " + str(id)
    return query
