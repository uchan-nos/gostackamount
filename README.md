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

つぎに，pprof を仕込んだ対象プログラムを起動し，goroutine のダンプを取得します．
一瞬で終了してしまうプログラムではこの手法は使えません．

    $ curl -s http://localhost:6060/debug/pprof/goroutine?debug=1 > goroutine.txt

最後に，2 つの情報を組み合わせてスタックフレーム毎のスタック消費量を算出します．

    $ ./goroutine_stack_amount.py stack_amount.tsv goroutine.txt

## 出力の読み方

`goroutine_stack_amount.py` コマンドの出力は次のようになります．

    1 @ 0x42e01a 0x42e0ce 0x449b96 0x6d7e88 0x42dbc2 0x45aa41
    #	0x449b95	time.Sleep+0x165	stack:96
    #	0x6d7e87	main.main+0x47	stack:32
    #	0x42dbc1	runtime.main+0x211	stack:88
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

goroutine はデフォルトで 4KiB のスタックを持ちます．
プログラムの実行に従ってスタックが消費され，足りなくなると 2 倍ずつ増えていきます．

Golang ではスタック領域はヒープ領域から取得されます．
goroutine が終了すると，一部のスタックはヒープ領域に戻されます．

スタック消費量の推定は，次のロジックで行います．
- スタックフレームの各関数が消費するスタック（M）の総和が 4KiB 未満なら，スタックフレーム 1 つが消費するスタック量は 4KiB とする．
- 各関数が消費するスタックの総和が 4KiB 以上であれば，2 の冪数に切り上げた数値をスタック量とする．

これで得られた 1 つのスタックフレームのスタック消費量に，そのスタックフレームを持つ goroutine の数（N）を掛けた数値を `total stack` として表示します．
