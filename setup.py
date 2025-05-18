from setuptools import setup, find_packages
import os

# Utility function to read the README file.
# Used for the long_description.
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname), encoding='utf-8').read()

# version.txtのパスを環境に合わせて指定
# Windowsの場合は "agesuta\\version.txt"
# Linux/macOSの場合は "agesuta/version.txt"
# os.path.joinを使うとクロスプラットフォームに対応できます
version_file_path = os.path.join("agesuta", "version.txt")

with open(version_file_path, "r") as f:
    version=f.read().replace("\n","").strip() # 空白文字も削除するようstrip()を追加

setup(
    name='agesuta',  # パッケージ名 (pip install時に使われる名前)
    version=version,        # パッケージのバージョン
    packages=find_packages(), # ディレクトリをパッケージとして自動検出
    install_requires=[      # このパッケージが依存する外部ライブラリ
        'certifi>=2025.4.26',
        'chardet>=5.2.0',
        'charset-normalizer>=3.4.2',
        'idna>=3.10',
        'markdown-it-py>=3.0.0',
        'mdurl>=0.1.2',
        'Pygments>=2.19.1',
        'requests>=2.32.3',
        'rich>=14.0.0',
        'slack_sdk>=3.35.0',
        'urllib3>=2.4.0',
    ],
    description='A custom logging utility and other utilities with Rich console output, file handling, Slack notification, etc.', # パッケージの簡単な説明 (更新)
    long_description=read('README.md'), # README.mdを詳細な説明として使用
    long_description_content_type='text/markdown', # long_descriptionの形式を指定
    url='https://github.com/AgemameSutachi/agesuta', # プロジェクトのリポジトリURL (任意)
    author='AgemameSutachi',        # 作者名 (任意)
    author_email='sutachiagemame@gmail.com', # 作者のメールアドレス (任意)
    license='MIT', # ライセンス (LICENSE ファイルを作成した場合)
    classifiers=[           # PyPIでの分類 (任意だが推奨)
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Logging',
        'Topic :: Communications :: Chat', # Slack連携に関連するトピックを追加
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    keywords='logging custom logger rich file rotation slack requests utility', # PyPIでの検索キーワード (更新)
    python_requires='>=3.6', # 必須Pythonバージョン

    # ここに package_data を追加します
    package_data={
        'agesuta': ['date.txt','version.txt'],
    },
)