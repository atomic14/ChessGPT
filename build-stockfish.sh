docker build . -t my-stockfish-image --platform=linux/amd64
docker create --name my-stockfish-container --platform=linux/amd64 my-stockfish-image  
docker cp my-stockfish-container:/var/task/Stockfish/src/stockfish stockfish
docker rm my-stockfish-container
docker rmi my-stockfish-image

