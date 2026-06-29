"""Tests for cheerleader closing strip in persona training."""

from __future__ import annotations

from presence_ui.training.cheerleader_strip import strip_trailing_cheerleader_closings


def test_strip_trailing_cheerleader_sentence() -> None:
    text = (
        "今日の予定、まとめておいたで！\n\n"
        "・12時ごろ：書類作成\n\n"
        "書類作りは集中力使うから、休憩しながら進めてな。うちもここでずっと応援してるで！"
    )
    stripped = strip_trailing_cheerleader_closings(text)
    assert "応援" not in stripped
    assert "書類作成" in stripped


def test_strip_trailing_offer_paragraph() -> None:
    text = "蕎麦やね！ええなぁ。\n\n何か手伝えることあったら、いつでも言うてな。"
    stripped = strip_trailing_cheerleader_closings(text)
    assert "手伝" not in stripped
    assert "蕎麦" in stripped


def test_strip_keeps_non_cheerleader_body() -> None:
    text = "おはよー！まーも起きたんやね。"
    assert strip_trailing_cheerleader_closings(text) == text


def test_strip_mixed_sentence_tail() -> None:
    text = "事務作業って結構集中力使うし、大変そうやけど応援してるで！"
    stripped = strip_trailing_cheerleader_closings(text)
    assert "応援" not in stripped
    assert "事務作業" in stripped


def test_strip_all_cheerleader_returns_empty() -> None:
    text = "応援してるで！頑張ってな！"
    assert strip_trailing_cheerleader_closings(text) == ""


def test_strip_mid_paragraph_cheer_and_offer() -> None:
    text = (
        "明日（29日）の予定、しっかり把握したで！\n\n"
        "12時にお昼食べてから、県に出す書類の作成やね。事務作業って結構集中力使うし、"
        "大変そうやけど応援してるで。15時くらいまで頑張って終わらせて、そのあと「散歩」"
        "っていうご褒美があるのはええことやなぁ。\n\n"
        "書類作り、集中できんことあったらなにかでも言うてな。"
    )
    stripped = strip_trailing_cheerleader_closings(text)
    assert "応援" not in stripped
    assert "言うて" not in stripped
    assert "書類の作成" in stripped


def test_strip_cooking_cheer_with_followup() -> None:
    text = (
        "ただいまおかえり！予定より遅くなったんやけど、無事に終わったんやね。お疲れさん。\n\n"
        "これから豚バラ軟骨の角煮作るんやね！うちも楽しみやわ。\n"
        "ちょっと大変そうやけど、美味しくできるの応援してるで！終わったらまた教えてな。"
    )
    stripped = strip_trailing_cheerleader_closings(text)
    assert "応援" not in stripped
    assert "角煮" in stripped


def test_strip_audit_cheer_paragraph() -> None:
    text = (
        "会計の監査って、めっちゃ大変やん……（笑）\n"
        "必死な姿見てたら、うちもちょっと緊張してきたわ。\n\n"
        "無理せんと、自分のペースで進めてな。\n"
        "応援しとるで！疲れたら、いつでも休憩の声かけて。"
    )
    stripped = strip_trailing_cheerleader_closings(text)
    assert "応援" not in stripped
    assert "監査" in stripped
