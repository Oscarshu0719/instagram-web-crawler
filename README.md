# instagram-web-crawler

## Instruction

Instagram web crawler. Download images and videos from specific users. 

## Change log

-   2019.10.20 - Add 'Download from saved' function.
-   2019.10.21 - Reconstruct code and it's able to download videos.
-   2019.10.22 - Add output of progress during fetching URLs and fix minor bugs.

## TODO

-   Download media which are in the specified period.

## Usage

-   Download [Chromedriver](https://chromedriver.chromium.org/downloads) first. Unzip it and put `chromedriver.exe` in folder `/bin`. 

-   Copy `secret.py.dist` as `secret.py` in the same folder.

```
python instagran_web_crawler.py [*path*] [--saved] 

Args:
        *path*: Input path (a file including one user_id per line).
        --saved: Download from saved.
```

### Input file format

```
*username* [*start_date*] [*end_date*]

(If *end_date* is specific and no specific *start_dat*e, use '-'. 
If *start_date* is specific and no specific *end_date*, 
no other input is needed.)
(Default: Posts of all time.)
```

#### Examples

```
a123456789 2019-01-01 2019-06-01
b987654321 2018-01-01 2019-01-01
c111111111 - 2019-02-01
d222222222 2019-03-01
e333333333
```

## Requirements

-   `python3`.
-    Details are in `conf/requirements.txt` .

## License

MIT License.
