# widevine_downloader


크롬 개발자 모드 활성화

압축해제된 확장 프로그램을 로드합니다. 클릭

ROOT\widevine_downloader\server\extension\widevine-l3-guesser
clearkey 추출

ROOT\widevine_downloader\server\extension\netflix-1080p
넷플릭스 1080p, 5.1채널 음성 가능하게 해줌
재생정보 확인 단축키 : ctrl + alt + shift + d


    # url_regex : UI에서 입력한 url을 매칭하기 위한 정규식
    # request_url_regex : 서버에서 받은 url로 매칭하기 위한 정규식
    # 카카오의 경우 웹브라우저 url을 요청 url로 바꾸어 서버에 전송하기 때문에 정규식이 다름



## 티빙
  - URL 형식 : 
    - https://www.tving.com/vod/player/E003573944, 
    - https://www.tving.com/movie/player/M000363046
  - MPEG-DASH / Segment
  - MPD : 영상, 음성 하나씩
  - 자막 : 영상에 포함
  - Segment
    ```
    "segment_templates": {
        "media": "QualityLevels($Bandwidth$,as=audio_und)/Fragments(audio_und=$Time$,format=dash)",
        "initialization": "QualityLevels($Bandwidth$,as=audio_und)/Fragments(audio_und=i,format=dash)",
    }
    ```
  - 화질별 MPD가 다름. 그래서 재생 후 최고화질로 변경해 줘야 함.
    이 설정값이 driver에서는 저장이 안됨.
    process 종료 후 재실행시 저장하지 않아 매번 720이 재생. 
    do_driver_action 에서 시작시 메뉴 탑으로 설정.
    mpd 선택은 reverse로 되기 때문에 기본 로직에 태워도 상관 없음.



## 쿠팡
  - MPEG-DASH / Segment
  - MPD : 여러개의 영상, 음성. 자막 포함
  - Segment
     ```
     $RepresentationID$/3x/segment$Number$.m4f
     ```
  - Number는 그냥 순차 대입 후 404 에러 발생시 중단.


## 카카오TV
  - MPEG-DASH / Segment
  - MPD : 여러개의 영상, 음성. 자막 포함
    Representation 자식에 SegmentTemplate이 있음
    ```
    <AdaptationSet id="1" lang="ko" contentType="audio" segmentAlignment="true" bitstreamSwitching="true">
        <Representation audioSamplingRate="44100" mimeType="audio/mp4" codecs="mp4a.40.2" id="a_t0_96-44100" bandwidth="98637">
            <AudioChannelConfiguration schemeIdUri="urn:mpeg:dash:23003:3:audio_channel_configuration:2011" value="2"/>
                <SegmentTemplate timescale="44100" presentationTimeOffset="0" duration="176400" startNumber="0" media="a_t0_96-44100/$Number%06d$.m4s" initialization="a_t0_96-44100/init.m4s"/>
    ```
  - Number형
  - 무료는 non-drm 그냥 로직에 태우고 decrypt때 실패하여 원본 그대로임
  - 유로는 1분만 다운로드

  
## 웨이브
  - MPEG-DASH / Segment
  - MPD : 여러개의 영상, 음성. 자막 영상에 포함
  - Segment
    ```
    "segment_templates": {
        "media": "$RepresentationID$/0/media_$Number$.m4s",
        "initialization": "$RepresentationID$/0/init.mp4",
    }
    ```
  - 다운로드시 쿠키 필수. 
  - startnumber 1. TODO: mpd에서 뽑아 적용


## 왓챠
  - MPEG-DASH / NOT Segment
  - MPD : 여러개의 영상, 음성. 자막
  - 자막별로 AdaptationSet 이 있음
    다른 것들은 하나의 AdaptationSet 안에 언어별로 Representation이 존재


## 넷플릭스
  - Disable VP9 codec 체크



## 라프텔

<SegmentTemplate timescale="30000" startNumber="1" media="video/avc1/2/seg-$Number$.m4s" initialization="video/avc1/2/init.mp4">

 <SegmentTemplate timescale="48000" startNumber="1" media="audio/mp4a/eng/seg-$Number$.m4s" initialization="audio/mp4a/eng/init.mp4">





## 리눅스 클라이언트 
  - aria2c

  apt install -y aria2

  apt install mkvtoolnix