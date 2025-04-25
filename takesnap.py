import maya.cmds as cmds # type: ignore
import os
import traceback # エラー詳細表示用
import tempfile # 一時ファイル作成用
import time # ファイル名用

class ViewportSnapshotTool:
    """
    ビューポートのスナップショットを撮影するためのGUIツールクラス (機能拡張版)。
    """
    WINDOW_NAME = "viewportSnapshotToolWindow"
    WINDOW_TITLE = "Viewport Snapshot Tool v0.5"

    # プレビュー画像のサイズ
    PREVIEW_WIDTH = 320
    PREVIEW_HEIGHT = 180

    def __init__(self):
        """
        クラスの初期化メソッド。UIの作成と初期設定を行います。
        """
        if cmds.window(self.WINDOW_NAME, exists=True):
            cmds.deleteUI(self.WINDOW_NAME, window=True)
        if cmds.workspaceControl(self.WINDOW_NAME + 'WorkspaceControl', exists=True):
             cmds.deleteUI(self.WINDOW_NAME + 'WorkspaceControl', control=True)

        # --- メンバー変数 (UIコントロールや状態保持用) ---
        self.filepath_field = None
        self.width_field = None
        self.height_field = None
        self.filter_menu = None
        self.display_mode_menu = None
        self.viewport_checkbox_group = None
        self.preview_image_control = None
        self.temp_preview_file = None # 一時プレビューファイルのパス
        self.available_model_panels = [] # 利用可能なモデルパネル名のリスト

        # --- デフォルト設定値 ---
        self.default_width = 1920
        self.default_height = 1080
        self.default_filter_key = 'all'
        self.default_display_mode_key = 'scene_objects' # 'viewport_all', 'selected_only', 'scene_objects'
        project_path = cmds.workspace(q=True, rd=True)
        images_dir = cmds.workspace(fileRuleEntry='images') or "images"
        self.default_filepath_base = os.path.join(project_path, images_dir, "snapshot") # ベース名のみ
        default_dir = os.path.dirname(self.default_filepath_base)
        if not os.path.exists(default_dir):
             user_docs = os.path.join(os.path.expanduser("~"), "Documents", "maya", "snapshots")
             self.default_filepath_base = os.path.join(user_docs, "snapshot")
             print(f"プロジェクトのimagesディレクトリが見つからないため、デフォルトパスを {user_docs} に設定します。")
        # 拡張子もデフォルトで持っておく
        self.default_extension = ".jpg"


        # --- UI要素の定義 ---
        self.window = cmds.window(self.WINDOW_NAME, title=self.WINDOW_TITLE, widthHeight=(500, 550), sizeable=True)

        # メインフォームレイアウト
        form = cmds.formLayout()
        # タブレイアウトを作成
        tabs = cmds.tabLayout(innerMarginWidth=5, innerMarginHeight=5)
        cmds.formLayout(form, edit=True, attachForm=((tabs, 'top', 0), (tabs, 'left', 0), (tabs, 'right', 0)))

        # --- タブ1: 基本設定 ---
        basic_tab = cmds.columnLayout("基本設定", adjustableColumn=True, rowSpacing=7, columnAttach=('both', 5))
        cmds.text(label="--- 保存設定 ---", align='left', font='boldLabelFont')

        # 1. ファイルパス設定 (ディレクトリ + ベース名)
        cmds.rowLayout(numberOfColumns=3, columnWidth3=(80, 350, 50), adjustableColumn=2,
                       columnAttach=[(1, 'right', 5), (2, 'both', 0), (3, 'both', 5)])
        cmds.text(label="保存フォルダ:")
        # 保存フォルダのパスを表示・編集（直接編集は非推奨かも）
        self.folder_path_field = cmds.textField(text=os.path.dirname(self.default_filepath_base), enable=True) # 表示のみにしたければ enable=False
        cmds.button(label="参照...", command=self.browse_folderpath)
        cmds.setParent('..')

        cmds.rowLayout(numberOfColumns=2, columnWidth2=(100, 300), adjustableColumn=2,
                       columnAttach=[(1, 'right', 5), (2, 'both', 0)])
        cmds.text(label="ベースファイル名:")
        self.filename_base_field = cmds.textField(text=os.path.basename(self.default_filepath_base), placeholderText="ファイル名の基本部分 (例: character_turn)")
        cmds.setParent('..')

        # 2. 解像度設定
        cmds.text(label="--- 出力設定 ---", align='left', font='boldLabelFont')
        cmds.rowLayout(numberOfColumns=4, columnWidth4=(80, 80, 80, 80),
                       columnAttach=[(1, 'right', 5), (2, 'left', 5), (3, 'right', 5), (4, 'left', 5)])
        cmds.text(label="幅 (Width):")
        self.width_field = cmds.intField(value=self.default_width, minValue=1, step=1)
        cmds.text(label="高さ (Height):")
        self.height_field = cmds.intField(value=self.default_height, minValue=1, step=1)
        cmds.setParent('..')

        # 3. オブジェクトフィルター設定 (以前のフィルター)
        cmds.rowLayout(numberOfColumns=2, columnWidth2=(100, 250), adjustableColumn=2,
                       columnAttach=[(1, 'right', 5), (2, 'both', 0)])
        cmds.text(label="オブジェクト種類:")
        self.filter_menu = cmds.optionMenu(label="")
        self.filter_options = {
            'すべて': 'all', 'メッシュのみ': 'mesh', 'ジョイントのみ': 'joint',
            'メッシュとジョイント': 'mesh_joint', 'NURBSのみ': 'nurbs',
        }
        for display_name in self.filter_options.keys():
            cmds.menuItem(label=display_name)
        default_display_name = next((dn for dn, key in self.filter_options.items() if key == self.default_filter_key), list(self.filter_options.keys())[0])
        cmds.optionMenu(self.filter_menu, edit=True, value=default_display_name)
        cmds.setParent('..')

        # 4. 表示モード設定 (新規追加)
        cmds.rowLayout(numberOfColumns=2, columnWidth2=(100, 250), adjustableColumn=2,
                       columnAttach=[(1, 'right', 5), (2, 'both', 0)])
        cmds.text(label="表示モード:")
        self.display_mode_menu = cmds.optionMenu(label="")
        self.display_mode_options = {
            'シーンオブジェクトのみ': 'scene_objects', # デフォルト (グリッド等オフ)
            'ビューポート全体': 'viewport_all',      # グリッド等含む
            '選択オブジェクトのみ': 'selected_only',   # 選択分離
        }
        for display_name in self.display_mode_options.keys():
            cmds.menuItem(label=display_name)
        default_display_name_mode = next((dn for dn, key in self.display_mode_options.items() if key == self.default_display_mode_key), list(self.display_mode_options.keys())[0])
        cmds.optionMenu(self.display_mode_menu, edit=True, value=default_display_name_mode)
        cmds.setParent('..')

        cmds.setParent('..') # basic_tab を抜ける

        # --- タブ2: ビューポート選択 ---
        viewport_tab = cmds.columnLayout("ビューポート選択", adjustableColumn=True, rowSpacing=5, columnAttach=('both', 5))
        cmds.text(label="スナップショットを撮るビューポートを選択してください:", align='left')
        # スクロール可能なレイアウト内にチェックボックスを配置
        scroll_layout = cmds.scrollLayout(horizontalScrollBarThickness=16, verticalScrollBarThickness=16, height=150)
        # チェックボックスグループ (縦並び)
        self.viewport_checkbox_group = cmds.columnLayout(adjustableColumn=True)
        self.update_viewport_list() # ビューポートリストを初期化
        cmds.setParent('..') # viewport_checkbox_group
        cmds.setParent('..') # scroll_layout
        cmds.setParent('..') # viewport_tab

        # --- タブ3: プレビュー ---
        preview_tab = cmds.columnLayout("プレビュー", adjustableColumn=True, rowSpacing=5, columnAttach=('both', 5))
        cmds.text(label="現在の設定でプレビューを表示 (最初の選択ビューポートが対象):", align='left')
        cmds.button(label="プレビュー更新", command=self.update_preview)
        # 画像表示エリア (中央揃えにするため frameLayout を使う)
        cmds.frameLayout(labelVisible=False, borderVisible=True, width=self.PREVIEW_WIDTH + 10, height=self.PREVIEW_HEIGHT + 10, collapsable=False, marginWidth=5, marginHeight=5)
        self.preview_image_control = cmds.image(width=self.PREVIEW_WIDTH, height=self.PREVIEW_HEIGHT, backgroundColor=(0.2, 0.2, 0.2))
        cmds.setParent('..') # frameLayout
        cmds.setParent('..') # preview_tab

        # --- タブレイアウトの終了 ---
        cmds.setParent('..') # tabs を抜ける (formLayoutに戻る)

        # --- 実行ボタンと閉じるボタン ---
        # ボタンをウィンドウ下部に配置するためのレイアウト
        button_layout = cmds.rowLayout(numberOfColumns=2, columnWidth2=(240, 240), columnAttach=[(1, 'both', 5), (2, 'both', 5)])
        cmds.formLayout(form, edit=True, attachForm=((button_layout, 'left', 5), (button_layout, 'bottom', 5), (button_layout, 'right', 5)),
                       attachControl=((button_layout, 'top', 5, tabs))) # タブの下にボタンを配置

        cmds.button(label="スナップショット撮影実行", command=self.execute_snapshot, height=40, backgroundColor=(0.6, 0.8, 0.6))
        cmds.button(label="閉じる", command=self.close_window, height=40)
        cmds.setParent( '..' ) # button_layout

        # ウィンドウ表示
        cmds.showWindow(self.window)

        # ウィンドウが閉じられたときに一時ファイルをクリーンアップするスクリプトジョブ
        cmds.scriptJob(uiDeleted=(self.window, self.cleanup_temp_file), protected=True)


    # --- GUI操作に対応するメソッド ---

    def browse_folderpath(self, *args):
        """保存フォルダ選択ダイアログを開く"""
        # fileMode=3: ディレクトリ選択モード
        start_dir = self.get_folder_path() or os.path.dirname(self.default_filepath_base)
        result = cmds.fileDialog2(dialogStyle=2, fileMode=3, caption="保存フォルダを選択", startingDirectory=start_dir)
        if result:
            folder_path = result[0]
            cmds.textField(self.folder_path_field, edit=True, text=folder_path)
            print(f"保存フォルダを設定: {folder_path}")
        else:
            print("フォルダ選択がキャンセルされました。")

    def update_viewport_list(self):
        """利用可能なモデルパネルをリストアップし、チェックボックスUIを更新"""
        # 現在のチェックボックスを削除
        children = cmds.columnLayout(self.viewport_checkbox_group, query=True, childArray=True)
        if children:
            for child in children:
                cmds.deleteUI(child)

        # 表示されているモデルパネルを取得
        self.available_model_panels = cmds.getPanel(type='modelPanel')
        visible_panels = cmds.getPanel(visiblePanels=True)
        # 表示されていて、かつモデルパネルであるものを抽出
        self.available_model_panels = [p for p in self.available_model_panels if p in visible_panels]

        if not self.available_model_panels:
            cmds.text(label="利用可能なビューポートが見つかりません。", parent=self.viewport_checkbox_group)
            return

        # 各パネルに対してチェックボックスを作成
        for panel_name in self.available_model_panels:
            # パネルのカメラ名を取得してラベルに表示 (例: modelPanel4 (persp))
            try:
                camera = cmds.modelEditor(panel_name, query=True, camera=True)
                label = f"{panel_name} ({camera})"
            except:
                label = panel_name # カメラ取得失敗時はパネル名のみ
            # チェックボックスを作成し、親をグループに設定
            cmds.checkBox(label=label, value=True, parent=self.viewport_checkbox_group,
                          # データをチェックボックス自体に保持（後で取得するため）
                          annotation=panel_name) # annotation にパネル名を保存


    def get_selected_viewports(self):
        """チェックされたビューポート名のリストを返す"""
        selected_panels = []
        children = cmds.columnLayout(self.viewport_checkbox_group, query=True, childArray=True)
        if children:
            for cb in children:
                if cmds.checkBox(cb, query=True, exists=True) and cmds.checkBox(cb, query=True, value=True):
                    # annotation に保存したパネル名を取得
                    panel_name = cmds.checkBox(cb, query=True, annotation=True)
                    selected_panels.append(panel_name)
        return selected_panels

    def update_preview(self, *args):
        """プレビュー画像を生成して表示"""
        print("\n--- プレビュー更新開始 ---")
        selected_panels = self.get_selected_viewports()
        if not selected_panels:
            cmds.warning("プレビュー対象のビューポートが選択されていません。")
            cmds.image(self.preview_image_control, edit=True, image="")
            print("プレビュー対象なし。更新処理を中断します。")
            return

        target_panel = selected_panels[0]
        print(f"プレビュー対象パネル: {target_panel}")

        width = self.PREVIEW_WIDTH
        height = self.PREVIEW_HEIGHT
        filter_key = self.get_filter_key()
        mode_key = self.get_display_mode_key()
        print(f"プレビュー設定 - Filter: '{filter_key}', Mode: '{mode_key}', Resolution: {width}x{height}")

        if mode_key == 'selected_only':
            current_selection = cmds.ls(selection=True)
            if not current_selection:
                cmds.warning("'選択オブジェクトのみ' モードですが、何も選択されていません。プレビューは更新されません。")
                cmds.image(self.preview_image_control, edit=True, image="")
                print("選択オブジェクトなしのため、プレビュー処理を中断します。")
                return

        # --- 一時ファイルの準備 ---
        self.cleanup_temp_file()
        try:
            # 最初に仮の一時ファイルパスを生成 (playblastのfilename引数に渡すため)
            temp_fd, initial_temp_path = tempfile.mkstemp(suffix=".jpg", prefix="maya_preview_")
            os.close(temp_fd)
            # self.temp_preview_file は generate_snapshot 内で実際のパスに更新される *可能性がある*
            self.temp_preview_file = initial_temp_path # 初期パスとして保持
            print(f"一時プレビューファイル 初期期待パス: {self.temp_preview_file}")

            # --- スナップショット生成の実行 ---
            snapshot_success = False
            try:
                # generate_snapshot を呼び出す (内部で self.temp_preview_file が更新される)
                self.generate_snapshot(
                    panel=target_panel,
                    filepath=self.temp_preview_file, # 初期期待パスを渡す
                    width=width,
                    height=height,
                    display_filter=filter_key,
                    display_mode=mode_key,
                    is_preview=True
                )
                snapshot_success = True # エラーなく完了
            except Exception as gen_e:
                 cmds.warning(f"スナップショット生成中にエラーが発生しました: {gen_e}")
                 print("generate_snapshot で例外発生:")
                 print(traceback.format_exc())
                 snapshot_success = False

            # --- 結果の確認と画像表示 (self.temp_preview_file が実際のパスになっていることを期待) ---
            if snapshot_success and self.temp_preview_file and os.path.exists(self.temp_preview_file):
                file_size = os.path.getsize(self.temp_preview_file)
                print(f"一時ファイル確認 (更新後): 存在します。パス: {self.temp_preview_file}, サイズ: {file_size} bytes")
                if file_size > 0:
                    print(f"画像コントロール '{self.preview_image_control}' を更新します...")
                    try:
                        cmds.image(self.preview_image_control, edit=True, image=self.temp_preview_file)
                        print("画像コントロールの更新コマンドを実行しました。")
                    except Exception as img_e:
                        cmds.warning(f"画像コントロールの更新中にエラー: {img_e}")
                        print(f"cmds.image 更新エラー: {traceback.format_exc()}")
                        cmds.image(self.preview_image_control, edit=True, image="")
                else:
                    cmds.warning("プレビュー画像は生成されましたが、中身が空のようです (ファイルサイズ 0)。表示設定を確認してください。")
                    print("ファイルサイズが0のため、プレビューは表示されません。")
                    cmds.image(self.preview_image_control, edit=True, image="")
            else:
                if snapshot_success:
                    print(f"警告: スナップショット生成は成功しましたが、最終的な一時ファイルが見つからないか無効です: {self.temp_preview_file}")
                else:
                    print("スナップショット生成に失敗したため、プレビューは表示されません。")
                cmds.warning("プレビュー画像の生成または表示に失敗しました。")
                cmds.image(self.preview_image_control, edit=True, image="")

        except Exception as e:
            cmds.warning(f"プレビュー処理全体で予期せぬエラーが発生しました: {e}")
            print("プレビュー処理の包括的エラー:")
            print(traceback.format_exc())
            cmds.image(self.preview_image_control, edit=True, image="")
        finally:
            print("--- プレビュー更新処理終了 ---")

    def cleanup_temp_file(self, *args):
        """一時プレビューファイルを削除"""
        # 以前のコードのままでOK
        if hasattr(self, 'temp_preview_file') and self.temp_preview_file:
            if os.path.exists(self.temp_preview_file):
                try:
                    os.remove(self.temp_preview_file)
                    print(f"一時ファイルを削除しました: {self.temp_preview_file}")
                except OSError as e:
                    print(f"一時ファイルの削除に失敗しました: {self.temp_preview_file}. エラー: {e}")
            self.temp_preview_file = None
    def execute_snapshot(self, *args):
        """「スナップショット撮影実行」ボタンの処理"""
        print("\n--- スナップショット処理開始 ---")
        # UIから設定値を取得
        folder_path = self.get_folder_path()
        filename_base = self.get_filename_base()
        width = self.get_width()
        height = self.get_height()
        filter_key = self.get_filter_key()
        mode_key = self.get_display_mode_key()
        selected_panels = self.get_selected_viewports()

        # --- バリデーション ---
        if not folder_path or not filename_base:
            cmds.warning("保存フォルダとベースファイル名を指定してください。")
            return
        if width <= 0 or height <= 0:
            cmds.warning("幅と高さは1以上の整数で指定してください。")
            return
        if not selected_panels:
            cmds.warning("スナップショットを撮るビューポートを少なくとも1つ選択してください。")
            return

        # --- ディレクトリ存在確認・作成 ---
        if not os.path.exists(folder_path):
            try:
                response = cmds.confirmDialog(
                    title='フォルダ作成確認', message=f'指定されたフォルダが存在しません:\n{folder_path}\n\n作成しますか？',
                    button=['はい', 'いいえ'], defaultButton='はい', cancelButton='いいえ', dismissString='いいえ')
                if response == 'はい':
                    os.makedirs(folder_path)
                    print(f"フォルダを作成しました: {folder_path}")
                else:
                    cmds.warning("フォルダが存在しないため、処理を中止しました。")
                    return
            except OSError as e:
                cmds.warning(f"フォルダの作成に失敗しました: {folder_path}. エラー: {e}")
                return

        # --- 各選択ビューポートに対して処理を実行 ---
        success_files = []
        error_panels = []
        for panel_name in selected_panels:
            print(f"\nビューポート '{panel_name}' の処理を開始...")
            try:
                # ファイル名を生成 (ベース名 + パネル名 + 拡張子)
                # パネル名からカメラ名を取得してファイル名に含める方がわかりやすいかも
                try:
                    cam_name = cmds.modelEditor(panel_name, query=True, camera=True)
                    # ファイル名に使えない文字を置換 (例: | を _)
                    safe_cam_name = cam_name.replace('|', '_').replace(':', '_')
                    filename_suffix = f"_{safe_cam_name}"
                except:
                    filename_suffix = f"_{panel_name}"

                # タイムスタンプを追加して一意性を高める（オプション）
                # timestamp = time.strftime("%Y%m%d_%H%M%S")
                # full_filename = f"{filename_base}{filename_suffix}_{timestamp}{self.default_extension}"
                full_filename = f"{filename_base}{filename_suffix}{self.default_extension}"
                filepath = os.path.join(folder_path, full_filename)

                print(f"  ファイルパス: {filepath}")
                print(f"  解像度: {width} x {height}")
                print(f"  オブジェクトフィルター: {filter_key}")
                print(f"  表示モード: {mode_key}")

                # スナップショット生成メソッド呼び出し
                self.generate_snapshot(
                    panel=panel_name,
                    filepath=filepath,
                    width=width,
                    height=height,
                    display_filter=filter_key,
                    display_mode=mode_key,
                    is_preview=False # 本番撮影
                )
                success_files.append(filepath)
                print(f"ビューポート '{panel_name}' の処理完了。")

            except Exception as e:
                error_msg = f"ビューポート '{panel_name}' の処理中にエラーが発生しました。"
                cmds.warning(error_msg)
                print(f"エラー詳細: {e}")
                print(traceback.format_exc())
                error_panels.append(panel_name)

        # --- 最終結果の表示 ---
        if success_files:
            msg = f"{len(success_files)} 件のスナップショットを保存しました。\n最初のファイル:\n{success_files[0]}"
            if len(success_files) > 1:
                 msg += f"\n...他 {len(success_files) - 1} 件"
            cmds.inViewMessage(amg=msg, pos='midCenter', fade=True, fadeStayTime=4000)

        if error_panels:
            cmds.warning(f"{len(error_panels)} 件のビューポートでエラーが発生しました: {', '.join(error_panels)}\n詳細はスクリプトエディタを確認してください。")

        print("\n--- 全スナップショット処理完了 ---")


    def close_window(self, *args):
        """ウィンドウを閉じる"""
        # scriptJob が呼ばれるので、ここではUI削除のみ
        if cmds.window(self.WINDOW_NAME, exists=True):
            cmds.deleteUI(self.WINDOW_NAME, window=True)
        if cmds.workspaceControl(self.WINDOW_NAME + 'WorkspaceControl', exists=True):
            cmds.deleteUI(self.WINDOW_NAME + 'WorkspaceControl', control=True)
        print(f"ウィンドウ '{self.WINDOW_NAME}' を閉じました。")


    # --- UI要素から値を取得するヘルパーメソッド ---
    def get_folder_path(self):
        return cmds.textField(self.folder_path_field, query=True, text=True)

    def get_filename_base(self):
        return cmds.textField(self.filename_base_field, query=True, text=True)

    def get_width(self):
        return cmds.intField(self.width_field, query=True, value=True)

    def get_height(self):
        return cmds.intField(self.height_field, query=True, value=True)

    def get_filter_key(self):
        selected_display_name = cmds.optionMenu(self.filter_menu, query=True, value=True)
        return self.filter_options.get(selected_display_name, 'all')

    def get_display_mode_key(self):
        selected_display_name = cmds.optionMenu(self.display_mode_menu, query=True, value=True)
        return self.display_mode_options.get(selected_display_name, 'scene_objects')


# --- スナップショット撮影のコア機能 (generate_snapshot) ---
    def generate_snapshot(self, panel, filepath, width, height, display_filter, display_mode, is_preview=False):
        """
        指定された設定でビューポートのスナップショットを撮影する内部メソッド。
        (playblastの戻り値の #### 置換対応)
        """
        print(f"\n--- generate_snapshot 開始: パネル='{panel}', ファイル='{filepath}' ---")
        if not cmds.modelPanel(panel, exists=True):
             print(f"エラー: 指定されたパネル '{panel}' が存在しません。")
             raise ValueError(f"指定されたパネル '{panel}' が存在しません。")

        def is_isolate_select_available(target_panel):
            try: cmds.isolateSelect(target_panel, query=True); return True
            except: return False

        # --- 1. 元の表示設定を保存 --- (変更なし)
        original_settings = {}
        isolation_state = False
        isolate_available = is_isolate_select_available(panel)
        flags_to_query = [
            'allObjects', 'polymeshes', 'nurbsSurfaces', 'nurbsCurves', 'subdivSurfaces',
            'planes', 'lights', 'cameras', 'joints', 'ikHandles', 'deformers',
            'dynamicConstraints', 'locators', 'dimensions', 'handles', 'pivots',
            'textures', 'strokes', 'fluids', 'follicles', 'hairSystems',
            'nCloths', 'nParticles', 'nRigids',
            'displayAppearance', 'displayTextures', 'displayLights', 'shadows',
            'wireframeOnShaded', 'xray', 'jointXray',
            'grid', 'hud', 'manipulators'
        ]
        print(f"[{panel}] 元の設定を保存中...")
        queried_count = 0
        for flag in flags_to_query:
            try: original_settings[flag] = cmds.modelEditor(panel, query=True, **{flag: True}); queried_count += 1
            except RuntimeError: pass
        print(f"[{panel}] {queried_count} 項目の設定を保存しました。")
        if isolate_available:
            try: isolation_state = cmds.isolateSelect(panel, query=True, state=True); print(f"[{panel}] 元の Isolate Select 状態: {isolation_state}")
            except Exception as iso_e: print(f"[{panel}] 元の Isolate Select 状態の取得に失敗: {iso_e}"); isolation_state = False
        else: print(f"[{panel}] Isolate Select はこのパネルでは利用できません。")

        # --- try...finally ---
        try:
            # --- 2. 表示設定の変更 --- (変更なし)
            print(f"[{panel}] 表示設定を変更中: Filter='{display_filter}', Mode='{display_mode}'")
            show_ornaments = True
            isolate_activated = False
            if display_mode == 'scene_objects': show_ornaments = False
            elif display_mode == 'viewport_all': show_ornaments = True
            elif display_mode == 'selected_only':
                show_ornaments = False
                current_selection = cmds.ls(selection=True, long=True)
                if current_selection and isolate_available:
                    try: cmds.isolateSelect(panel, state=True); isolate_activated = True
                    except Exception as iso_e: print(f"[{panel}] Isolate Select の有効化に失敗: {iso_e}")
                elif not current_selection: print(f"[{panel}] '選択オブジェクトのみ' モードですが、選択がありません。(generate_snapshot)")
                elif not isolate_available: print(f"[{panel}] '選択オブジェクトのみ' モードですが、Isolate Select が利用できません。")
            settings_to_disable = {
                'allObjects': False, 'polymeshes': False, 'nurbsSurfaces': False, 'nurbsCurves': False,
                'subdivSurfaces': False, 'planes': False, 'lights': False, 'cameras': False,
                'joints': False, 'ikHandles': False, 'deformers': False, 'dynamicConstraints': False,
                'locators': False, 'manipulators': False, 'dimensions': False, 'handles': False,
                'pivots': False, 'textures': False, 'strokes': False, 'fluids': False, 'follicles': False,
                'hairSystems': False, 'nCloths': False, 'nParticles': False, 'nRigids': False
            }
            cmds.modelEditor(panel, edit=True, **settings_to_disable)
            settings_to_enable = {}
            if display_filter == 'all': settings_to_enable['allObjects'] = True
            elif display_filter == 'mesh': settings_to_enable.update({'polymeshes': True, 'subdivSurfaces': True})
            elif display_filter == 'joint': settings_to_enable['joints'] = True
            elif display_filter == 'mesh_joint': settings_to_enable.update({'polymeshes': True, 'subdivSurfaces': True, 'joints': True})
            elif display_filter == 'nurbs': settings_to_enable.update({'nurbsCurves': True, 'nurbsSurfaces': True})
            else: settings_to_enable['allObjects'] = True
            if settings_to_enable: cmds.modelEditor(panel, edit=True, **settings_to_enable)

            # --- 3. スナップショット撮影 ---
            print(f"[{panel}] Playblast 実行準備: 解像度={width}x{height}, 装飾={show_ornaments}")
            current_time = int(cmds.currentTime(query=True)) # フレーム番号は整数で取得
            start_frame = current_time # 静止画なので開始フレーム番号を保持
            print(f"[{panel}] Playblast (初期期待パス): {filepath}")
            actual_filepath_raw = None # playblastからの生の戻り値
            try:
                actual_filepath_raw = cmds.playblast(
                    activeEditor=False, editorPanelName=panel,
                    startTime=start_frame, endTime=start_frame, # 開始・終了フレームを指定
                    format='image',
                    filename=filepath,
                    sequenceTime=0, clearCache=True, viewer=False,
                    showOrnaments=show_ornaments, offScreen=True, forceOverwrite=True,
                    framePadding=4, # #### に合わせてパディングを4に (重要)
                    percent=100, quality=100, widthHeight=[width, height]
                )
                print(f"[{panel}] Playblast 正常終了。")
                print(f"[{panel}] Playblast 戻り値 (Raw): {actual_filepath_raw}")
            except Exception as pb_e:
                 print(f"[{panel}] !!! Playblast 実行中にエラーが発生しました: {pb_e}")
                 raise pb_e

            # --- ▼▼▼ ファイルパス処理 (#### 置換対応) ▼▼▼ ---
            final_filepath = None
            path_to_check = None

            # 戻り値がリストか文字列かチェック
            if isinstance(actual_filepath_raw, (list, tuple)) and actual_filepath_raw:
                path_to_check = actual_filepath_raw[0] # リストなら最初の要素
            elif isinstance(actual_filepath_raw, str) and actual_filepath_raw:
                path_to_check = actual_filepath_raw # 文字列ならそのまま
            else:
                # 戻り値が無効な場合は期待パスでチェック (フォールバック)
                print(f"[{panel}] 警告: Playblastの戻り値が無効 ({actual_filepath_raw})。期待パス ({filepath}) で確認します。")
                path_to_check = filepath

            # path_to_check が有効な文字列か確認
            if isinstance(path_to_check, str):
                # "####" が含まれているかチェック
                if "####" in path_to_check:
                    try:
                        # start_frame を使って #### を置換
                        # framePadding=4 なので、4桁ゼロ埋め
                        frame_str = str(start_frame).zfill(4)
                        final_filepath = path_to_check.replace("####", frame_str)
                        print(f"[{panel}] ファイルパスの #### を置換: {path_to_check} -> {final_filepath}")
                    except Exception as fmt_e:
                        print(f"[{panel}] !!! #### の置換中にエラー: {fmt_e}")
                        final_filepath = None # 置換失敗
                else:
                    # #### が含まれていない場合はそのまま使用
                    final_filepath = path_to_check
            else:
                 print(f"[{panel}] 警告: 有効なファイルパス文字列が得られませんでした。")
                 final_filepath = None

            # --- ファイルチェック ---
            if final_filepath and os.path.exists(final_filepath):
                file_size = os.path.getsize(final_filepath)
                print(f"[{panel}] ファイル生成確認: 存在します。パス: {final_filepath}, サイズ: {file_size} bytes")
                if is_preview:
                    initial_temp_path = filepath
                    if initial_temp_path != final_filepath and os.path.exists(initial_temp_path):
                        try: os.remove(initial_temp_path); print(f"[{panel}] 初期期待パスのファイルを削除: {initial_temp_path}")
                        except OSError as e: print(f"[{panel}] 初期期待パスファイルの削除に失敗: {e}")
                    self.temp_preview_file = final_filepath
                    print(f"[{panel}] プレビュー用一時ファイルパスを更新: {self.temp_preview_file}")
            else:
                if final_filepath:
                    print(f"[{panel}] !!! 警告: Playblast後、最終的なファイルが見つかりません: {final_filepath}")
                else:
                    print(f"[{panel}] !!! 警告: 有効なファイルパスが決定できなかったため、ファイルを確認できませんでした。")
                if is_preview:
                    self.temp_preview_file = None
                    print(f"[{panel}] プレビュー用一時ファイルパスを None に設定しました。")
            # --- ▲▲▲ ファイルパス処理完了 ▲▲▲ ---

        except Exception as e:
            print(f"[{panel}] !!! generate_snapshot 処理中にエラーが発生: {e}")
            raise e

        finally:
            # --- 4. 表示設定の復元 --- (変更なし)
            print(f"[{panel}] 表示設定を復元中...")
            try:
                if isolate_activated and isolate_available:
                    try:
                        current_iso_state_before_restore = cmds.isolateSelect(panel, query=True, state=True)
                        if current_iso_state_before_restore != isolation_state:
                             cmds.isolateSelect(panel, state=isolation_state)
                             print(f"[{panel}] Isolate Select の状態を元 ({isolation_state}) に戻しました。")
                    except Exception as iso_e: print(f"[{panel}] Isolate Select の復元中にエラー: {iso_e}")

                if original_settings:
                    valid_settings = {k: v for k, v in original_settings.items() if v is not None}
                    if valid_settings:
                        cmds.modelEditor(panel, edit=True, **valid_settings)
                        print(f"[{panel}] modelEditor 設定 ({len(valid_settings)}項目) を復元しました。")
                else: print(f"[{panel}] 警告: 元の modelEditor 設定が保存されていませんでした。")

            except Exception as e: print(f"[{panel}] !!! 表示設定の復元中にエラーが発生しました: {e}")

            print(f"--- generate_snapshot 終了: パネル='{panel}' ---")
if __name__ == "__main__":
    try:
        snapshot_tool_instance = ViewportSnapshotTool()
    except Exception as e:
        print(f"ツールの起動に失敗しました: {e}")
        print(traceback.format_exc())
