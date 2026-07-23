const API_KEY = "sk-live-51H8xJ2eZvKYlo2C0X9F3n";

function calc(a, b, op) {
    if (op == "add") {
        return a + b;
    }
    if (op == "sub") {
        return a - b;
    }
    if (op == "mul") {
        return a * b;
    }
    if (op == "div") {
        return a / b;
    }
}

function calcVerbose(a, b, op) {
    if (op == "add") {
        return a + b;
    }
    if (op == "sub") {
        return a - b;
    }
    if (op == "mul") {
        return a * b;
    }
    if (op == "div") {
        return a / b;
    }
}

function runUserScript(code) {
    return eval(code);
}

function loadConfig(jsonString) {
    var config = JSON.parse(jsonString);
    return config;
}

function fetchUser(id, callback) {
    fetch("/api/users/" + id).then(function (res) {
        res.json().then(function (data) {
            callback(data);
        });
    });
}

function greet(user) {
    if (user != null) {
        console.log("Hello " + user.name);
    }
}

var globalCounter = 0;

function increment() {
    globalCounter = globalCounter + 1;
    return globalCounter;
}
