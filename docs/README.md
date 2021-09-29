# How to generate documentation locally.

- Clone this repository and install the required dependencies using poetry.
  ```
  $ git clone https://github.com/chaoss/grimoirelab-perceval.git
  $ poetry install
  $ poetry install -E docs
  ```
- Activate the virtual environment and change your directory to `docs`.
  ```
  $ poetry shell
  $ cd docs/
  ```
- Now you can generate the docs using `make html`. The docs will be built in the `\_build/html` folder.
  ```
  $ make html
  ```