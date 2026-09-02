"""
plugins/_template.py — EDITH Eklenti Şablonu

Bu dosyayı kopyalayın, adını değiştirin (başında alt çizgi olmadan, örn: `zar_at.py`),
`PLUGIN` ve `run()` alanlarını doldurun.

EDITH başlatıldığında eklentinizi otomatik olarak tanıyacaktır.
"""

PLUGIN = {
    "name": "ornek_eklenti",                     # snake_case, benzersiz olmalı
    "description": (
        "Eklentinin ne işe yaradığını ve LLM'in bu aracı ne zaman çağırması gerektiğini açıklayın. "
        "Örnek tetikleyici cümleleri belirtin."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "ornek_parametre": {
                "type": "STRING",
                "description": "Parametrenin açıklaması"
            },
        },
        "required": [],   # Zorunlu parametreler listesi (boş bırakılabilir)
    },
}


def run(parameters: dict = None, player=None, session_memory=None) -> str:
    """
    Eklenti tetiklendiğinde çalıştırılacak ana fonksiyon.

    Args:
        parameters: LLM tarafından gönderilen argümanlar sözlüğü
        player: Opsiyonel medya/ses oynatıcı referansı
        session_memory: Opsiyonel oturum belleği referansı

    Returns:
        str: Kullanıcıya veya asistana dönecek metin sonucu
    """
    params = parameters or {}
    deger = params.get("ornek_parametre", "varsayılan")
    
    # Eklenti mantığınızı buraya yazın
    print(f"[OrnekPlugin] Çalıştırıldı, parametre: {deger}")
    return f"Örnek eklenti başarıyla çalıştı! Parametre değeri: {deger}"
