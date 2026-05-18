import requests
from bs4 import BeautifulSoup

# 1. 페이지 가져오기
url = "https://sports.daum.net/schedule/kbo" # 특정 날짜 지정
response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(response.text, 'html.parser')

# 2. 큰 그물: 모든 경기 덩어리(리스트) 찾기
# (class명이 'list_game'이라고 가정)
games = soup.find_all('li', class_='list_game')

# 3. 뜰채: 각 경기에서 데이터 뽑아내기
for game in games:
    # 아직 안 한 경기나 우천 취소 등 예외 처리를 위해 try-except 사용
    try:
        # 홈팀 정보
        home_team = game.find('div', class_='team_home').find('span', class_='txt_team').text
        home_score = int(game.find('div', class_='team_home').find('em', class_='num_score').text)
        
        # 원정팀 정보
        away_team = game.find('div', class_='team_away').find('span', class_='txt_team').text
        away_score = int(game.find('div', class_='team_away').find('em', class_='num_score').text)
        
        print(f"{home_team} ({home_score}) vs ({away_score}) {away_team}")
        
    except AttributeError:
        # 점수가 없거나(우천취소, 경기전) 태그가 다르면 무시하고 넘어감
        print("경기가 없거나 아직 시작하지 않았습니다.")