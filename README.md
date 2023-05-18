# ChessGPT

A plugin for ChatGPT that should let it play a better game of chess.

One of the problems that ChatGPT has is that it can forget where the pieces are on the board as it has no memory. This leads to it starting to make illegal moves.

This plugin should help it remember where the pieces are (though it still sometimes forgets!) and also provides a nice display of the board.

~~One very important thing that we don't want to do, is to help ChatGPT pick better moves. We're just trying to provide it with more context so that it can keep track of the game and display it to the user. ChatGPT should always be the one choosing which move to make.~~

I've concluded that the above is not really what we want to do. We want to give the user of the plugin the best experience and use ChatGPT to help them play a better game of chess. So I've added in the stockfish engine to help ChatGPT pick better moves.

## Usage

## Running locally

You'll need to have developer access to the ChatGPT plugins.

If you don't have access then you can watch a video of it in action here: https://youtu.be/lXFeq2yUy58

[![ChessGPT](https://img.youtube.com/vi/lXFeq2yUy58/0.jpg)](https://youtu.be/lXFeq2yUy58)

To run the plugin locally and test it follow these commands. You can then install it into ChatGPT.

```
docker compose up
```

```
sls dynamodb migrate
```

You'll also need stockfish installed (adjust this for your platform)

```
brew install stockfish
```

```
IS_OFFLINE=True sls wsgi serve -p 5204
```

## Deploying

You can also deploy it to AWS using the Serverless framework.

```
AWS_PROFILE=serverless sls deploy   
```

## Testing

Install the dev requirements

```
pip install -r requirements-dev.txt
```

Now run pytest

```
pytest
```

## How does it work?

We're using the amazing [python-chess](https://python-chess.readthedocs.io/en/v0.2.0/index.html) library to do all the heavy lifting.

We don't want to help ChatGPT pick better moves - we're just trying to provide it information so that it can keep track of the game and display it to the user.

To handle multiple games from many conversations and users we're using DynamoDB to store the game state.

This lets us pull back the game for a conversation and update it with the latest move.

To display the game we send back an SVG of the game at a particular move index.

## TODO

At the moment, ChatGPT can still lose track of the positions of the pieces - more research is needed to work out the best way to give it more context - or more useful context.

There are no unit tests and the code is definitely not production ready - use at your own risk!