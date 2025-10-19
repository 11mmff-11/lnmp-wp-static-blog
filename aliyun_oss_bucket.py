import os
import oss2
from dotenv import load_dotenv
from prettytable import PrettyTable
from pathlib import Path  

load_dotenv("aliyun_env")

def conn_oss_bucket():
    try:
        access_key_id=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
        access_key_secret=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        endpoint=os.getenv("ENDPOINT")
        bucket_name=os.getenv("BUCKET_NAME")
     
        required_params={"ALIBABA_CLOUD_ACCESS_KEY_ID":access_key_id,"ALIBABA_CLOUD_ACCESS_KEY_SECRET": access_key_secret,
                       "ENDPOINT":endpoint,"BUCKET_NAME":bucket_name} #定义一个字典

        missing_params=[k for k,v in required_params.items() if not v] #通过一个列表生成式来检验是否缺少环境变量的配置，如果v是空值(如果v是没有内容的，也就是空值时)的话则对应的k进入该列表

        if missing_params:                                                              
           raise ValueError(f"缺少必要的环境变量配置：{', '.join(missing_params)}\n" # 整个if语句表示如果列表不为空时(如果列表是有内容的)，代表上述字典中的k键所对应的v是空值，所以k键才会进入该列表
                             "请检查aliyun_env文件是否正确设置这些参数")
        
        auth=oss2.Auth(access_key_id,access_key_secret) #实例化对象，进行身份验证（通过accesskey）

        bucket=oss2.Bucket(auth,endpoint,bucket_name) #实例化对象，通过身份验证以及绑定所对应的那个bucket存储空间
        bucket.list_objects(max_keys=1) #实例化对象bucket使用oss2.Bucket这个类的list_objects方法，作用是列出bucket存储空间中的一个文件，尝试性的检验是否连接到对应的bucket

        return bucket
           
    except Exception as e:

        print(f"OSS连接初始化失败：{str(e)}")
        return None

def oss_bucket_list(bucket,prefix="",delimiter="/"):   #bucket表示连接到的Bucket存储空间，prefix表示寻找一个以“ ”为前缀的文件，delimter表示以“/”代表目录，实际上不存在目录，这里是逻辑上的目录。
    try:
        table=PrettyTable()  #实例化对象（创建一个这个类的对象),生成格式化表格，避免纯文本输出杂乱。
        table.field_names=["文件名", "大小(字节)", "最后修改时间", "ETag"]    #调用这个类的方法，创建一个列表形式的字段属性
        count=0
        for obj in oss2.ObjectIterator(bucket, prefix=prefix, delimiter=delimiter):  #遍历整个bucket，oss2.ObjectIterator自动分页获取bucket内容，避免内存溢出
            count += 1
        if isinstance(obj,oss2.models.ObjectInfo):  #判断遍历的这个object是否是ObjectInfo（这个类表示“文件”，包含文件的路径、大小等信息)这个类的
           table.add_row([
                          obj.key,
                          obj.size,                #如果是则在表格中增加一行数据
                          obj.last_modified,
                          obj.etag
           ])
        elif isinstance(obj, oss2.models.CommonPrefix):  #当object是oss2.models.CommonPrefix这个类，这个类表示“目录前缀”，模拟“目录”，只有目录的路径信息。
                table.add_row([f"[目录] {obj.prefix}", "", "", ""])
        
        print(f"OSS Bucket '{bucket.bucket_name}' 中的文件列表 (共 {count} 项):")
        print(table)
        return True
    except Exception as e:
        print(f"列出文件失败：{str(e)}")
        return False
          
def upload_oss_bucket(bucket,local_file_path,oss_object_key):
    try:
        if not os.path.exists(local_file_path):   #检查本地文件是否存在
           raise FileNotFoundError(f'本地文件不存在，上传错误:{local_file_path}')
          
        if not os.path.isfile(local_file_path):  #检查本地文件是否是目录
           raise IsADirectoryError(f'指定路径是目录，不是文件：{local_file_path}')
        
        #上传文件
        result=bucket.put_object_from_file(oss_object_key,local_file_path)
        #检验上传文件的结果
        if result.status == 200:
           print(f'上传文件成功，状态为:{result.status}')
           file_size=os.path.getsize(local_file_path)
           print(f"本地文件：{local_file_path}（大小：{file_size}字节）")
           print(f"OSS路径：{oss_object_key}")
           print(f"ETag：{result.etag}")  # ETag可用于验证文件完整性
           return True
        else:
            print(f"❌ 文件上传失败，状态码：{result.status}")
            return False
    except Exception as e:
           print(f"❌ 上传失败：{str(e)}")
           return False

def download_from_oss(bucket, oss_object_key, local_file_path):
    try:
        #需要检查本地下载的目录是否存在
        local_dir = os.path.dirname(local_file_path)  #该函数的作用是返回本地目录中去除文件名之外的目录信息
        if local_dir and not os.path.exists(local_dir): #这个if语句需要同时满足两个条件，1.local_dir1不是空值是有内容的，比如本地路径是a.txt,只有文件名没有其他目录信息，那么上一行代码只会返回空值。
                                                                         #第二个条件就是本地路径是不存在的
           Path(local_dir).mkdir(parents=True, exist_ok=True)  #如果满足if语句的条件表达式，则会触发该方法，会根据本地路径创建一个多级目录(parents=True)，且当目录已存在时不会报错(exist_ok=True)
           print(f"创建本地目录：{local_dir}")
        #开始下载文件              
        result=bucket.get_object_to_file(oss_object_key,local_file_path)
        #验证下载结果
        if os.path.exists(local_file_path):
           print(f'文件下载成功')
           file_size=os.path.getsize(local_file_path)
           print(f"OSS路径：{oss_object_key}")
           print(f"本地保存：{local_file_path}（大小：{file_size}字节）")
           print(f"最后修改时间：{result.last_modified}")
           return True  
        else:
            print(f"❌ 下载失败，本地文件未生成")
            return False
    except oss2.exceptions.NoSuchKey:
           print(f"❌ 下载失败：OSS中不存在该文件 - {oss_object_key}")
           return False
    except Exception as e:
           print(f"❌ 下载失败：{str(e)}")
           return False

def main_menu():
    """主菜单交互函数"""
    print("\n===== OSS文件管理工具 =====")
    print("1. 列出OSS中的文件和目录")
    print("2. 上传本地文件到OSS")
    print("3. 从OSS下载文件到本地")
    print("0. 退出程序")
    return input("请选择操作（0-3）：")


if __name__ == "__main__":
    # 初始化OSS连接
    bucket = conn_oss_bucket()
    
    if not bucket:
        print("无法连接到OSS，程序退出")
        exit(1)
    
    # 主循环
    while True:
        choice = main_menu()
        
        if choice == "1":
            # 列出文件
            prefix = input("请输入要列出的目录前缀（留空则列出所有）：")
            oss_bucket_list(bucket, prefix=prefix)
            
        elif choice == "2":
            # 上传文件
            local_path = input("请输入本地文件路径（如：./test.jpg）：")
            oss_path = input("请输入OSS中的保存路径（如：images/test.jpg）：")
            upload_oss_bucket(bucket,local_path,oss_path)
            
        elif choice == "3":
            # 下载文件
            oss_path = input("请输入OSS中的文件路径（如：images/test.jpg）：")
            local_path = input("请输入本地保存路径（如：./downloads/test.jpg）：")
            download_from_oss(bucket, oss_path,local_path )
            
        elif choice == "0":
            print("程序已退出")
            break
            
        else:
            print("无效的选择，请重新输入")

