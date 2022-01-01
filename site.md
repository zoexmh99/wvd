# widevine_downloader

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
  - 세그먼트 다운로드시 IP 체크 및 쿠키 필수
  - 


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



## 디즈니플러스
  - HLS
  - 영상, 음성, 자막 메니페스트 파일이 각각 있음.
  - 이것들에 앞서 목록을 보여주는 메니페스트도 있지만 최대 720고정
  - 하나의 m3u8에 여러 mp4 들이 세그먼트가 포함됨.
    - 메인 작품에 대한 세그먼트가 있지만, 오리지널인 경우 3초짜리 디즈니 로고가 나오는 영상이 포함됨.
    - 작품이 끝나는 구간에서는 제공사에 대한 영상들도 포함
    - 이것들은 분리하여 메인작품에 대한 것만 합쳐야함



## 시즌
  - HLS
  - 비트레이별 영상, 음성 따로 있음. 자막 영상에 포함
  - 미리보기시에도 전체에 대한 목록을 주고 세그먼트 다운로드도 가능
  - TODO: 디즈니 코드에서 약간만 변경. 추후 HLS 사이트 포함시 DASH처럼 공통 모듈로 처리 할 것






## 리눅스 클라이언트 
  - aria2c

  apt install -y aria2

  apt install mkvtoolnix