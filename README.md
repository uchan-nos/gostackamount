# gostackamount

Golang で作ったプログラムの，各 goroutine が消費するスタックサイズを見積もるためのツールです．
pprof で取得できる goroutine のスタックフレーム情報を，バイナリを解析して得られた関数のスタック消費量に照らし合わせて算出します．

## 用途

Golang 製プログラムのスタック消費量を見積もりたい場合に使えます．

Golang 標準の [pprof](https://golang.org/pkg/net/http/pprof/) パッケージではヒープメモリの詳細なプロファイルを取ることが可能ですが，スタックの使用状況に関する情報は得られません．
本ツールにより各 goroutine により何バイトのスタックが消費されているかを見積もることができます．

[MemStats](https://golang.org/pkg/runtime/#MemStats) により得られる StackInuse 値が大きい場合，このツールの解析結果が役立つはずです．
MemStats は [expvar](https://golang.org/pkg/expvar/) パッケージを利用すると簡単に取得できます．

## 使い方

まず，対象とする Golang プログラムを逆アセンブルして関数毎のスタック消費量を見積もります．

    $ objdump -d -M intel your-binary | ./stack_amount.py > stack_amount.tsv

`your-binary` は対象とする Golang 製プログラムへのパスを指定します．`objdump -d` は対称のプログラムを逆アセンブルします．
`stack_amount.py` コマンドは，現状では x86-64 向けバイナリ（の逆アセンブル結果）にのみ対応しています．

出力された `stack_amount.tsv` には，関数名，その関数のアドレス範囲，その関数が消費するスタック量が記載されています．

つぎに，pprof を仕込んだ対象プログラムを起動し，goroutine のダンプを取得します．
一瞬で終了してしまうプログラムではこの手法は使えません．

    $ curl -s http://localhost:6060/debug/pprof/goroutine?debug=1 > goroutine.txt

最後に，2 つの情報を組み合わせてスタックフレーム毎のスタック消費量を算出します．

    $ ./goroutine_stack_amount.py stack_amount.tsv goroutine.txt

## 出力の読み方

`goroutine_stack_amount.py` コマンドの出力は次のようになります．

    1 @ 0x42e01a 0x42e0ce 0x449b96 0x6d7e88 0x42dbc2 0x45aa41
    #	0x42e01a	runtime.gopark	stack:32
    #	0x42e0ce	runtime.goparkunlock	stack:64
    #	0x449b96	time.Sleep	stack:96
    #	0x6d7e88	main.main	stack:32
    #	0x42dbc2	runtime.main	stack:88
    #	0x45aa41	runtime.goexit	stack:8
    total stack (estimated): 4096

    1 @ ...

空行によりスタックフレームが区切られています．1 つのスタックフレームについて説明します．

1 行目の形式は `N @ 関数アドレス群` です．N は，同じスタックフレームを持つ goroutine の数を表します．
多くの goroutine は複数起動され，同じ場所でブロックされることが多いので，このようにまとめることに意味があります．

中間行（`#` から始まる行）はスタックフレームの本体です．
最も上の行が現在実行中（またはブロックされている）関数です．
下に行くほど上位の関数となります．

`stack:M` のように，各関数が消費するスタック量をバイト単位で出力します．

最終行は推定されたスタック消費量をバイト単位で出力します．

## スタック消費量の見積もり

### 関数単位のスタック消費量の見積もり

Golang の x86-64 用処理系は，ほとんどの関数について必要なスタックフレームを関数の先頭で確保するようにしているようです．
典型的には，次のように `sub` 命令を使ってスタックフレームを確保します．

    sub  rsp, 0x10

関数の先頭で 1 度だけ `rsp` から値を引くことでスタックフレームを確保します．
`stack_amount.py` コマンドの基本戦略は，その関数内で行われる `sub rsp` を見つけ出し，その第 2 オペランドの値を取得することです．

ほとんどのスタック消費は `sub rsp` により行われますが，それだけではありません．
関数は `call` 命令によって呼び出されるので，`call` 命令によるスタック消費（8 バイト）も考慮する必要があります．

まれに，`sub rsp` ではなく `push` 命令を使ってスタックを消費することもあるようです．
念のため，`stack_amount.py` は `push` が 8 バイトを消費すると仮定してスタック消費量としてカウントします．

以上をまとめると，`stack_amount.py` コマンドは次の値の和をその関数のスタック消費量として推定します．

- `sub rsp` の第 2 オペランド
- `push` が消費する 8 バイト
- `call` のための 8 バイト

### goroutine 単位のスタック消費量の見積もり

goroutine はデフォルトで 4KiB のスタックを持ちます．
プログラムの実行に従ってスタックが消費され，足りなくなると 2 倍ずつ増えていきます．

Golang ではスタック領域はヒープ領域から取得されます．
goroutine が終了すると，一部のスタックはヒープ領域に戻されます．

スタック消費量の推定は，次のロジックで行います．
- ある goroutine のスタックフレームの各関数が消費するスタック（M）の総和が 4KiB 未満なら，goroutine 1 つが消費するスタック量は 4KiB とする．
- 各関数が消費するスタックの総和が 4KiB 以上であれば，2 の冪数に切り上げた数値をスタック量とする．

これで得られた 1 つのスタックフレームのスタック消費量に，そのスタックフレームを持つ goroutine の数（N）を掛けた数値を `total stack` として表示します．
