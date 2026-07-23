#include <iostream>
#include <cstring>
using namespace std;

char globalBuffer[16];

void copyName(char* input) {
    strcpy(globalBuffer, input);
}

int* makeArray(int size) {
    int* arr = new int[size];
    for (int i = 0; i < size; i++) {
        arr[i] = i * 2;
    }
    return arr;
}

double compute(double x, double y, double z, double a, double b, double c, double d) {
    double r = 0;
    if (x > 0) { r = r + x * 3.14159; }
    if (y > 0) { r = r + y * 3.14159; }
    if (z > 0) { r = r + z * 3.14159; }
    if (a > 0) { r = r + a * 3.14159; }
    if (b > 0) { r = r + b * 3.14159; }
    if (c > 0) { r = r + c * 3.14159; }
    if (d > 0) { r = r + d * 3.14159; }
    return r;
}

double computeAgain(double x, double y, double z, double a, double b, double c, double d) {
    double r = 0;
    if (x > 0) { r = r + x * 3.14159; }
    if (y > 0) { r = r + y * 3.14159; }
    if (z > 0) { r = r + z * 3.14159; }
    if (a > 0) { r = r + a * 3.14159; }
    if (b > 0) { r = r + b * 3.14159; }
    if (c > 0) { r = r + c * 3.14159; }
    if (d > 0) { r = r + d * 3.14159; }
    return r;
}

void printValue(int* ptr) {
    cout << *ptr << endl;
}

int main() {
    char userInput[100];
    cout << "Enter your name: ";
    cin >> userInput;
    copyName(userInput);

    int* numbers = makeArray(10);
    printValue(numbers);

    cout << "Result: " << compute(1, 2, 3, 4, 5, 6, 7) << endl;

    return 0;
}
