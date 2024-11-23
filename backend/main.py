# main.py
from fastapi import FastAPI, Request, Response, Query
from models import RouteSearchRequest, StopResponse, Attraction  # models.pyからインポート
import requests
import json
import logging
from fastapi.middleware.cors import CORSMiddleware
import duckdb
import geohash2
from pydantic import BaseModel
import random
from typing import List

app = FastAPI()
#OTP_API_HOST = "http://localhost"
OTP_API_HOST = "https://rws7z95b-8080.asse.devtunnels.ms"
#OTP_API_PORT = 8080

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 必要に応じてオリジンを制限
    allow_credentials=True,
    allow_methods=["*"],  # 必要に応じてメソッドを制限
    allow_headers=["*"],  # 必要に応じてヘッダーを制限
)

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/otp/gtfs/rndstop", response_model=StopResponse)
async def get_random_stop(lat: float = Query(...), lon: float = Query(...)):
    # 駅検索用のジオハッシュを生成（精度4）
    geohash_stops = geohash2.encode(lat, lon, precision=4)
    logger.info(f"Generated geohash for stops: {geohash_stops}")

    # DuckDBに接続
    conn = duckdb.connect('RouteApp.duckdb')

    # geohashの前方一致検索で4桁が一致する駅を取得
    query_stops = f"""
    SELECT stop_code, stop_name, stop_lat, stop_lon, geohash
    FROM stops
    WHERE geohash LIKE '{geohash_stops}%'
    """
    stops = conn.execute(query_stops).fetchall()
    logger.info(f"Found stops: {stops}")

    # ランダムに1件選択
    if stops:
        stop = random.choice(stops)
        stop_code, stop_name, stop_lat, stop_lon, stop_geohash = stop
        stop_code = stop_code if stop_code is not None else ''  # stop_codeがNoneの場合は空文字列を設定
        stop_latlon = f"{stop_lat},{stop_lon}::{stop_lat},{stop_lon}"
        
        # 観光地検索用のジオハッシュを生成（精度5）
        geohash_attractions = stop_geohash[:6]
        logger.info(f"Generated geohash for attractions: {geohash_attractions}")

        # 観光地情報を取得
        attractions_query = f"""
        SELECT spot_name, category1, category2, longitude, latitude
        FROM merged_attractions
        WHERE geohash LIKE '{geohash_attractions}%'
        """
        attractions = conn.execute(attractions_query).fetchall()
        logger.info(f"Found attractions: {attractions}")
        
        attractions_list = [
            {
                "attraction_name": attraction[0],
                "attraction_category": attraction[1] if attraction[1] is not None else '',  # attraction_categoryがNoneの場合は空文字列を設定
                "attraction_lon": attraction[2],
                "attraction_lat": attraction[3]
            }
            for attraction in attractions
        ]
        
        return StopResponse(
            stop_code=stop_code,
            stop_name=stop_name,
            stop_lat=stop_lat,
            stop_lon=stop_lon,
            stop_latlon=stop_latlon,
            attractions=attractions_list
        )
    else:
        return Response(content="No stops found", status_code=404)

@app.post("/otp/gtfs/v1")
async def proxy_post(request: Request):
    # 生のリクエストボディをログに出力
    raw_body = await request.body()
    # logger.info(f"Received raw request body: {raw_body.decode('utf-8')}")

    try:
        # Pydanticモデルに変換
        request_data = RouteSearchRequest.parse_raw(raw_body)
    except Exception as e:
        logger.error(f"Error parsing request body: {str(e)}")
        return Response(content=f"Invalid request body: {str(e)}", status_code=422)

    headers = dict(request.headers)

    # fromPlaceとtoPlaceを変更可能な変数に設定
    from_place = request_data.variables.fromPlace
    to_place = request_data.variables.toPlace

    # GraphQLリクエストを構築
    graphql_query = {
        "query": request_data.query,
        "variables": {
            "arriveBy": request_data.variables.arriveBy,
            "banned": request_data.variables.banned,
            "bikeReluctance": request_data.variables.bikeReluctance,
            "carReluctance": request_data.variables.carReluctance,
            "date": request_data.variables.date,
            "fromPlace": from_place,
            "modes": [mode.dict() for mode in request_data.variables.modes],
            "numItineraries": request_data.variables.numItineraries,
            "preferred": request_data.variables.preferred,
            "time": request_data.variables.time,
            "toPlace": to_place,
            "unpreferred": request_data.variables.unpreferred,
            "walkReluctance": request_data.variables.walkReluctance,
            "walkSpeed": request_data.variables.walkSpeed,
            "wheelchair": request_data.variables.wheelchair
        }
    }

    # リクエストボディをJSON形式に変換
    modified_body = json.dumps(graphql_query)

    # OTPサーバーへのリクエストURL
    #otp_url = f"{OTP_API_HOST}:{OTP_API_PORT}/otp/routers/default/index/graphql"
    otp_url = f"{OTP_API_HOST}/otp/routers/default/index/graphql"
    logger.info(f"POST request to OTP URL: {otp_url}")
    # logger.info(f"Request body: {modified_body}")
    # logger.info(f"Request headers: {headers}")

    # OTPへのリクエスト送信
    otp_response = requests.post(otp_url, headers=headers, data=modified_body)
    
    # OTPサーバーからのレスポンス内容とコンテンツタイプを取得
    content_type = otp_response.headers.get("Content-Type", "application/json")
    
    # エラーチェック
    if otp_response.status_code != 200:
        logger.error(f"Error from OTP: {otp_response.status_code} - {otp_response.text}")
    
    return Response(content=otp_response.content, status_code=otp_response.status_code, media_type=content_type)