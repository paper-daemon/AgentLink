<!-- revenue-idempotency: github-guide-ai-agent-idempotency-safety-v1 -->
# AIエージェントの二重実行を防ぐ: idempotency と receipt の実務ガイド

AIエージェントがメール送信、ファイル更新、API書き込みなどの外部アクションを行うとき、怖いのは「失敗」だけではありません。タイムアウトや再開後に、実は成功していた処理をもう一度実行してしまうことがあります。

このガイドでは、AgentLink の公開デモでも使っている保守的な考え方を、一般的なAI自動化へ落とし込みます。

## 1. まず外部アクションに idempotency key を付ける

同じ論理アクションには、再試行しても同じキーを使います。

```text
send-proposal-client123-v1
publish-product-AL-CHK-001-v1
update-customer-record-8472-v3
```

キーは「実行ごと」ではなく「同じ副作用ごと」に固定します。新しい試行のたびに新しいキーを作ると、重複防止になりません。

## 2. 成功したら receipt を残す

最低限、次を保存します。

```json
{
  "idempotency_key": "send-proposal-client123-v1",
  "action": "email_send",
  "status": "completed",
  "provider_object_id": "message_123",
  "timestamp": "2026-08-28T12:00:00Z"
}
```

重要なのは、AIの会話ログだけに頼らないことです。可能ならメールの message ID、決済の PaymentIntent ID、Git commit SHA など、外部サービス側の識別子も残します。

## 3. 再開時は「もう一度やる」より先に照合する

再開判断は3種類に分けると安全です。

| 状態 | 動作 |
| --- | --- |
| 完了 receipt がある | 再実行しない |
| 未開始が確認できる | 実行してよい |
| 成功か失敗か不明 | 外部サービスを照合してから決める |

「不明」を自動的に「失敗」とみなさないことがポイントです。

## 4. 書き込み系は read-back verification を入れる

APIが200を返しても、可能なら直後に読み戻します。

例:

1. 商品ページを更新する
2. commit SHA を受け取る
3. 同じファイルを再取得する
4. 期待した内容と blob SHA を確認する
5. receipt を確定する

メールなら SENT フォルダ、決済なら provider の payment state など、サービス側の事実を照合します。

## 5. お金・契約・本人確認は別の境界にする

idempotency があっても、何でも自動化してよいわけではありません。少なくとも次は、通常の低リスク処理と別の権限境界に置く方が安全です。

- 送金・払い戻し・有料広告
- 契約の承諾
- KYC、税務、法的本人情報
- OTP / CAPTCHA などの本人確認

「技術的に実行できる」と「実行権限がある」を分離します。

## 6. 小さな pre-flight を毎回通す

外部アクション直前に、最低でも次を確認します。

- 同じ idempotency key の完了 receipt はないか
- 対象、金額、宛先、公開先は正しいか
- 必要な権限はあるか
- 個人情報や秘密情報を公開しないか
- 失敗時に照合できる provider ID を取得できるか

これだけでも「再開したAIが同じメールを二度送る」「商品リンクを重複作成する」といった事故をかなり減らせます。

## 公開デモ

AgentLink には、完了・未開始・不明の3状態から再実行判断を行う簡易デモがあります。

- [Receipt Replay Simulator](../demos/receipt-replay-simulator/)

## すぐ使えるチェックリスト

実運用向けの pre-flight、権限境界、incident recovery、idempotency log の考え方は、本ガイドと [idempotency-receipt-ledger](https://github.com/paper-daemon/idempotency-receipt-ledger) にまとめています（旧チェックリスト商品は提供終了）。

チェックリストは事故を完全に防ぐ保証ではありません。実際のシステムでは、利用するAPIや業務リスクに合わせて権限・監査・復旧設計を調整してください。
