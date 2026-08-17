"""첨부를 내려받아 텍스트를 뽑고, **못 읽은 것을 못 읽었다고 남긴다**(plan/07).

뽑은 텍스트로 무엇을 판단하지 않는다. 배점·요건·양식 추출은 F2-3 이후다.

  store.py    콘텐츠 주소 저장. 저장소를 옮길 때 바뀌는 유일한 파일(ADR-0022)
  formats.py  지원 포맷 목록과 내용 기반 확장자 판정
  hwp.py      HWP / HWPX / DOCX / PDF 추출기. spike/hwp_text.py 승격
  download.py 내려받기
  extract.py  해독 디스패치
  service.py  CLI 와 집계가 같이 쓰는 경로
"""
