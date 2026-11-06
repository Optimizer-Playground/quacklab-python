# quacklab Python adapter

The quacklab Python adapter integrates quacklab into the DuckDB Python package. quacklab is a research project to integrate
optimizer hints into DuckDB. These hints overwrite optimizer decisions like the join order or cardinality estimates:

```py
import quacklab
db = quacklab.connect("imdb.duckdb")
hints = "/*=quack_lab= card(t #42) card(mi #24) */"  # this comment will be embedded in the SQL query
db.sql(f"explain {hints} select count(*) from title t join movie_info mi on t.id = mi.movie_id where t.production_year < 2010")
```

## Repo Layout

The `quacklab-patches` branch is used to track our changes to upstream DuckDB. It should not be used directly.
For the DuckDB versions that we support, dedicated `quacklab-[DuckDB release]` branches exist, such as `quacklab-v2.0-cyanoptera`.
These branches are used to apply our quacklab patches to the specific DuckDB release. Use these branches to build quacklab.

## Installation

See the [quacklab repository](https://github.com/rbergm/quacklab.git) for information on the required software to compile
quacklab. In addition to these requirements, the DuckDB Python adapter also needs [uv](https://docs.astral.sh/uv/) to build
the Python package. For quacklab we adhere to the standard build process as far as possible.

The **TLDR** is

```bash
git clone --recurse-submodules https://github.com/rbergm/quacklab-python.git
cd quacklab-python
git fetch --tags
git switch quacklab-v2.0-cyanoptera
git submodule update --init --recursive
cd external/duckdb && git fetch --tags
cd ../..
uv build
```

Or to explain the individual steps:

1. Make sure you have tags available in the repository: `git fetch --tags`. Tags are used for versioning by the DuckDB build
   process.
2. Select the package version you want to build by checking out the corresponding branch, e.g.,
   `git switch quacklab-v2.0-cyanoptera`
3. Check out the matching quacklab submodule: `git submodule update --init --recursive`. Run this again whenever you switch
   to a different branch.
4. Make sure you have tags available in the quacklab submodule: `cd external/duckdb && git fetch --tags`
5. Back in the main directory, you can start the package build: `uv build`. This will automatically compile DuckDB/quacklab
   from source, so this process will take a while.
6. Install the quacklab wheel into whatever Python environment you want, e.g. using `pip install dist/quacklab-<suffix>.whl`.

The parser for the hinting grammar is checked into quacklab, so no Java runtime is needed for the build. If you change the
grammar, see the [quacklab repository](https://github.com/rbergm/quacklab.git) for how to regenerate the parser.

## Usage

The Python adapter can be used like the standard DuckDB package. Queries that contain hints are automatically processed by
quacklab. Refer to the official [DuckDB documentation](https://duckdb.org/docs/stable/clients/python/overview) and
[quacklab documentation](https://github.com/rbergm/quacklab.git) for details.
