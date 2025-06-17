@echo off
echo Установка всех зависимостей для Ollama + LangChain + Tools...

REM Основные библиотеки LangChain
pip install -U langchain langchain-community langchain-experimental langchain-ollama

REM Поисковик
pip install -U duckduckgo-search

REM Работа с PDF
pip install -U PyPDF2

REM Голосовой ввод
pip install -U SpeechRecognition

REM Озвучка (TTS)
pip install -U pyttsx3

pip install WMI
echo Установка завершена!
pause
