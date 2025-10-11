# 定义仓库和程序目录
REPO_DIR="/root/piaozone-chatbot"
PROGRAM="app.py"

while true; do
    # 进入仓库目录
    cd $REPO_DIR

    # 检测是否有更新
    git fetch
    UPSTREAM=${1:-'@{u}'}
    LOCAL=$(git rev-parse @)
    REMOTE=$(git rev-parse "$UPSTREAM")

    if [ $LOCAL != $REMOTE ]; then
        echo "$(date): 有更新，正在拉取..."
        git pull

        echo "$(date): 重启 Python 程序..."
        #pkill -f $PROGRAM
        sh start.sh 
        echo "$(date): 程序已重启"
    else
        echo "$(date): 没有更新"
    fi

    # 等待10秒
    sleep 9
done
