# Algorithm Practice Platform

A full-stack web application that evaluates Python algorithm solutions against curated test cases — similar in concept to LeetCode, but lightweight and built entirely from scratch using **FastAPI** and **React**.

## Overview
The platform allows users to write, submit, and test Python code for algorithmic problems directly in the browser.  
Submitted code is executed in a secure backend sandbox, which enforces time and memory limits while collecting execution statistics.  
The frontend provides a clean, interactive editor and displays detailed results for each submission.

## Tech Stack
- **Frontend:** React, JavaScript, HTML, CSS  
- **Backend:** FastAPI (Python)  
- **Execution Tools:** subprocess, psutil, tempfile  
- **Deployment (planned):** Docker + Render / Railway  

## Features
- Evaluate algorithm solutions in real time  
- Display detailed runtime and memory usage  
- Execute user code in a sandboxed environment with resource limits  
- Built-in problem sets across core topics: arrays, graphs, and sorting  
- Modular architecture for easily adding new problems and languages  
- Modern React-based interface for writing and viewing solutions  

## Future Enhancements
- Support for C++ and Java execution  
- Persistent user accounts and submission tracking  
- Leaderboards and performance analytics  
- Problem creation dashboard for instructors or researchers  
- Cloud deployment and database integration
