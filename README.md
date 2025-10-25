# Algorithm Practice Platform

A full-stack web application that evaluates Python algorithm solutions against curated test cases — similar in concept to LeetCode, but lightweight and built entirely from scratch using **FastAPI** and **React**.

## Overview
The platform allows users to write, submit, and test Python code for algorithmic problems directly in the browser.  
Submitted code runs securely in a backend sandbox with time and memory limits, and the frontend displays execution results clearly and interactively.

## Tech Stack
- **Frontend:** React, JavaScript, HTML, CSS  
- **Backend:** FastAPI (Python)  
- **Execution Tools:** subprocess, psutil, tempfile  
- **Deployment (planned):** Docker + Render / Railway  

## Features
- Evaluate Python code in real time  
- Display runtime and memory usage  
- Execute code securely with resource limits  
- Include built-in algorithm problems (arrays, graphs, sorting)  
- Provide clean, responsive UI for writing and testing solutions  

## Next Steps
- Add multiple test case support per problem  
- Improve error handling and performance metrics  
- Implement basic user session tracking  
- Expand the problem library gradually
