#导入读取环境变量的库(工具)
import os
from dotenv import load_dotenv
# 导入阿里云ECS SDK的客户端和配置
from alibabacloud_ecs20140526.client import Client as EcsClient
from alibabacloud_tea_openapi.models import Config
from alibabacloud_ecs20140526.models import DescribeInstancesRequest
# 3. 导入阿里云SDK的错误处理
#from alibabacloud_tea import TeaException,解释不能安装对应的包或库，导致捕获异常不能使用

# 4. 加载AccessKey（从aliyun_env文件读，安全）
load_dotenv("aliyun_env")
region_id = os.getenv("ECS_REGION_ID")
print("Region ID:", region_id)  
print("AccessKey ID:", os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"))
print("AccessKey Secret:", os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"))

def ecs_list():
    try:
        config=Config(             #调用alibabacloud_tea_openapi.models模块中的Config类，赋值给创建的对象config
        access_key_id=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        access_key_secret=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        region_id=os.getenv("ECS_REGION_ID"))
        
        
        client=EcsClient(config) #创建client对象，实现EcsClient类中所定义的所有方法。
        print("✅ 成功登录阿里云ECS API！")
        
        # 调用API查ECS实例（DescribeInstances是查实例的接口），这里给response这个对象赋值了client对象使用了describe_instances()方法后的返回值
        
        request = DescribeInstancesRequest()  # 新增：创建请求对象
        request.region_id = os.getenv("ECS_REGION_ID")
        response = client.describe_instances(request=request)  # 传入request
        # 解析结果（从API返回的内容里提取ECS信息）
        aliyun_ecs_list = response.body.instances.instance  # API返回的ECS列表
        if not ecs_list:
            print("⚠️ 没查到ECS实例")
            return
        print("\n📋 ECS实例列表：")
        for idx, ecs in enumerate(aliyun_ecs_list, 1):
            print(f"{idx}. ECS ID: {ecs.instance_id}, 状态: {ecs.status}")

     
   
        
        # 常见错误：NoPermission=权限不足，InvalidAccessKeyId=AccessKey错了
    except Exception as e:
        print(f"❌ 其他错误：{e}")

if __name__ == "__main__":
    ecs_list()
