# **Algorithm Practice Platform**

A full-stack web application that evaluates Python algorithm solutions against curated test cases — similar to LeetCode, but lightweight and built from scratch using **FastAPI** and **React**.

---

## **Overview**
The platform allows users to write Python code, submit it, and view pass/fail results with execution statistics.  
The backend executes the code securely in a sandbox with time and memory limits, while the frontend provides an interactive code editor and results display.

---

## **Tech Stack**
- **Frontend:** React, JavaScript, HTML, CSS  
- **Backend:** FastAPI (Python)  
- **Execution Tools:** `subprocess`, `psutil`, `tempfile`  
- **Deployment:** (planned) Docker + Render / Railway  

---

## **Features**
- Evaluates algorithm solutions in real time  
- Displays runtime and memory usage  
- Includes built-in problems (arrays, graphs, sorting)  
- FastAPI backend executes user code safely  
- React frontend provides an editor and output panel
