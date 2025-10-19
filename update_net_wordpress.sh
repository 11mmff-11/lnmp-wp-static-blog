#!/bin/bash

#该脚本主要是用来改变/usr/share/nginx/html/wp-config.php中的配置，有关wordpress的数据库的信息；
#第二作用是修改mariadb数据库中的wordpress数据库中某个表中对ecs主机外网记录；
#第三个作用是修改wordpress后端FTP的限制，使nginx用户可对wordpress拥有写权限，以便安装一些插件等；

#定义变量
DB_HOST="localhost"
DB_USER="root"
DB_NAME="wordpress"
DB_PASSWORD="200512"
ECS_NEW_IP="123.57.250.223"
WP_CONFIG_PATH="/usr/share/nginx/html/wp-config.php"
WP_ROOT_DIR="/usr/share/nginx/html"
#定义函数：查询文件是否存在

check_file_exists(){

  if [ ! -f "${WP_CONFIG_PATH}" ] ; then
     echo "文件不存在，请检查文件路径是否正确"
     exit 1
  fi
}

#定义函数：修改wp-config.php文件中的内容

update_wp_config(){
 #检查文件是否存在
 check_file_exists "${WP_CONFIG_PATH}"
 
 
 #开始更新文件内容
 sed -i "s/define( 'DB_HOST', '.*' );/define( 'DB_HOST', '${DB_HOST}' );/g" "${WP_CONFIG_PATH}"
 sed -i "s/define( 'DB_USER', '.*' );/define( 'DB_USER', '${DB_USER}' );/g" "${WP_CONFIG_PATH}"
 sed -i "s/define( 'DB_NAME', '.*' );/define( 'DB_NAME', '${DB_NAME}' );/g" "${WP_CONFIG_PATH}"
 sed -i "s/define( 'DB_PASSWORD', '.*' );/define( 'DB_PASSWORD', '${DB_PASSWORD}' );/g" "${WP_CONFIG_PATH}"
 echo "更新文件成功，您可以开始服务"
}

#定义函数：修改数据库中的信息

update_db_config(){
 echo "正在更新数据库中的站点URL..."

 #构建sql语句
 SQL_COMMENT="USE ${DB_NAME};
 UPDATE wp_options SET option_value = 'http://"${ECS_NEW_IP}"' WHERE option_name = 'siteurl';
 UPDATE wp_options SET option_value = 'http://"${ECS_NEW_IP}"' WHERE option_name = 'home';
 "

 #执行sql语句
 echo "${SQL_COMMENT}" | mysql -u "${DB_USER}" -p  -h"${DB_HOST}"

  # 检查命令是否执行成功
 if [ $? -eq 0 ]; then
    echo "数据库URL更新完成"
 else
    echo "错误：数据库URL更新失败"
    exit 1
 fi
}

#定义函数：修改文件及目录权限
update_file_mod(){
 echo "正在修改目录权限"
 
 #检查目录是否存在
 if [ ! -d  "${WP_ROOT_DIR}" ] ; then
    echo "目录不存在，请检查文件路径是否正确"
    exit 1
 fi
 chown -R nginx:nginx "${WP_ROOT_DIR}"

 find "$WP_ROOT_DIR" -type d -exec chmod 755 {} \;
 find "$WP_ROOT_DIR" -type f -exec chmod 644 {} \;
    
 echo "目录权限更新完成"
}
main(){
 echo "开始WordPress ECS配置..."
 echo "当前配置的新IP地址: "$ECS_NEW_IP""
 update_wp_config
 update_db_config
 update_file_mod
 echo "所有配置步骤完成！WordPress应该可以正常使用了。"
}

main
