"""위경도 -> 기상청 단기예보 격자(nx, ny). 기상청 활용가이드의 LCC 변환식."""
import math
def to_grid(lat, lon):
    RE, GRID, SLAT1, SLAT2, OLON, OLAT, XO, YO = 6371.00877, 5.0, 30.0, 60.0, 126.0, 38.0, 43, 136
    D = math.pi / 180.0; re = RE / GRID
    s1, s2, ol, oa = SLAT1 * D, SLAT2 * D, OLON * D, OLAT * D
    sn = math.log(math.cos(s1) / math.cos(s2)) / math.log(math.tan(math.pi/4 + s2/2) / math.tan(math.pi/4 + s1/2))
    sf = math.tan(math.pi/4 + s1/2) ** sn * math.cos(s1) / sn
    ro = re * sf / math.tan(math.pi/4 + oa/2) ** sn
    ra = re * sf / math.tan(math.pi/4 + lat*D/2) ** sn
    th = lon * D - ol
    th = th - 2*math.pi if th > math.pi else th + 2*math.pi if th < -math.pi else th
    th *= sn
    return int(ra * math.sin(th) + XO + 0.5), int(ro - ra * math.cos(th) + YO + 0.5)
if __name__ == "__main__":
    print("서울시청", to_grid(37.5665, 126.9780))
