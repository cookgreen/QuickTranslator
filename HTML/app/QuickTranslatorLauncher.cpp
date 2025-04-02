#include <windows.h>
#include <iostream>
#include <string>
#include <filesystem>
#include <cstdlib>
#include <tlhelp32.h>
#include <algorithm>

bool fileExists(const std::string& path) {
    return std::filesystem::exists(path);
}

bool isProcessRunning(const std::string& processName) {
    // Create a snapshot of currently running processes
    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) {
        return false;
    }

    PROCESSENTRY32 pe32;
    pe32.dwSize = sizeof(PROCESSENTRY32);

    // Get the first process
    if (!Process32First(hSnapshot, &pe32)) {
        CloseHandle(hSnapshot);
        return false;
    }

    // Iterate through all processes
    do {
        // Convert CHAR array to std::string first
        std::string processNameStr(pe32.szExeFile);
        // Then convert std::string to std::wstring if needed
        std::wstring wProcessName(processNameStr.begin(), processNameStr.end());
        std::string currentProcess(wProcessName.begin(), wProcessName.end());
        
        // Convert to lowercase for case-insensitive comparison
        std::transform(currentProcess.begin(), currentProcess.end(), currentProcess.begin(), ::tolower);
        std::string lowerProcessName = processName;
        std::transform(lowerProcessName.begin(), lowerProcessName.end(), lowerProcessName.begin(), ::tolower);
        
        if (currentProcess.find(lowerProcessName) != std::string::npos) {
            CloseHandle(hSnapshot);
            return true;
        }
    } while (Process32Next(hSnapshot, &pe32));

    CloseHandle(hSnapshot);
    return false;
}

int main() {
    SetConsoleTitleA("QuickTranslator Launcher");
    
    std::cout << "===================================" << std::endl;
    std::cout << "      QuickTranslator Launcher     " << std::endl;
    std::cout << "===================================" << std::endl;
    std::cout << std::endl;
    
    // Current directory path
    char currentDir[MAX_PATH];
    GetCurrentDirectoryA(MAX_PATH, currentDir);
    std::cout << "Working directory: " << currentDir << std::endl;
    
    // Check if Chrome exists
    std::string chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
    if (!fileExists(chromePath)) {
        std::cout << "Error: Chrome not found at " << chromePath << std::endl;
        std::cout << "Please install Chrome or update the path in the launcher." << std::endl;
        std::cout << "Press any key to exit..." << std::endl;
        std::cin.get();
        return 1;
    }
    
    // Check if Python is installed
    std::string pythonCommand = "python --version";
    int pythonCheck = system(pythonCommand.c_str());
    if (pythonCheck != 0) {
        std::cout << "Error: Python is not installed or not in PATH." << std::endl;
        std::cout << "Please install Python and make sure it's in your PATH." << std::endl;
        std::cout << "Press any key to exit..." << std::endl;
        std::cin.get();
        return 1;
    }
    
    // 1. Start Chrome with the local URL
    std::string chromeCommand = "start "" \"" + chromePath + "\" http://localhost:8000/";
    std::cout << "Launching browser..." << std::endl;
    system(chromeCommand.c_str());
    
    // 2. Start Python HTTP server
    std::cout << "Starting HTTP server on port 8000..." << std::endl;
    std::cout << "Press Ctrl+C to stop the server." << std::endl;
    system("python -m http.server 8000");
    
    return 0;
}