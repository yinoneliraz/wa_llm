#!/bin/bash

echo "Starting ruff test"
uvx ruff check

echo "Starting black"
uvx black .

echo "starting pyright"
uvx pyright